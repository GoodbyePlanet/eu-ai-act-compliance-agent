"""Business logic for request-unit billing and account bootstrap."""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from compliance_agent.billing.db import get_session_factory
from compliance_agent.billing.models import (
    BillingUser,
    CreditAccount,
    CreditLedgerEntry,
    LedgerReason,
    StripeCustomer,
)

logger = logging.getLogger(__name__)

REQUEST_UNIT_PRICE_EUR = 0.2


class InsufficientCreditsError(Exception):
    """Raised when a user has no request units left."""


@dataclass(frozen=True)
class CreditState:
    """Current user request-unit balances."""

    request_units_balance: int
    free_request_units_remaining: int
    paid_request_units_remaining: int
    can_run_request: bool
    stripe_customer_exists: bool
    request_unit_price_eur: float


@dataclass(frozen=True)
class BillingUserRef:
    """Minimal internal user reference for billing flows."""

    id: str
    email: str


class BillingService:
    """Service for all billing and request-unit operations."""

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        self._session_factory = session_factory or get_session_factory()

        # Default signup grant is 5 request units (1 credit).
        self._free_request_units = int(os.getenv("FREE_REQUEST_UNITS_ON_SIGNUP", "5"))

    async def ensure_user(self, google_sub: str, email: str) -> BillingUserRef:
        """Create or retrieve user/account and grant one-time free request units."""
        try:
            return await self._ensure_user_once(google_sub=google_sub, email=email)
        except IntegrityError:
            # Rare concurrent first-login race: retry once.
            return await self._ensure_user_once(google_sub=google_sub, email=email)

    async def _ensure_user_once(self, google_sub: str, email: str) -> BillingUserRef:
        async with self._session_factory() as session:
            async with session.begin():
                user = await self._get_user_for_update(session=session, google_sub=google_sub)
                if user is None:
                    user = BillingUser(google_sub=google_sub, email=email)
                    session.add(user)
                    await session.flush()

                user.email = email

                account = await session.get(CreditAccount, user.id, with_for_update=True)
                if account is None:
                    account = CreditAccount(user_id=user.id, balance=0)
                    session.add(account)

                if user.free_credits_granted_at is None:
                    account.balance += self._free_request_units
                    user.free_credits_granted_at = datetime.now(timezone.utc)
                    session.add(
                        CreditLedgerEntry(
                            user_id=user.id,
                            delta=self._free_request_units,
                            reason=LedgerReason.FREE_GRANT,
                            balance_after=account.balance,
                            metadata_json={"source": "signup"},
                            idempotency_key=f"free-grant:{user.id}",
                        )
                    )
            return BillingUserRef(id=user.id, email=user.email)

    async def consume_credit_for_request(
        self,
        *,
        user_id: str,
        request_id: str,
        session_id: Optional[str],
        ai_tool: str,
    ) -> int:
        """Atomically consume one request unit for each accepted assessment request."""
        async with self._session_factory() as session:
            async with session.begin():
                idempotency_key = f"request-debit:{user_id}:{request_id}"
                existing_stmt: Select = select(CreditLedgerEntry.id).where(
                    CreditLedgerEntry.idempotency_key == idempotency_key
                )
                existing = (await session.execute(existing_stmt)).scalar_one_or_none()
                if existing is not None:
                    return await self._balance_for_user(session=session, user_id=user_id)

                account = await session.get(CreditAccount, user_id, with_for_update=True)
                if account is None or account.balance < 1:
                    raise InsufficientCreditsError("No request units left. Buy credits to continue.")

                account.balance -= 1
                session.add(
                    CreditLedgerEntry(
                        user_id=user_id,
                        delta=-1,
                        reason=LedgerReason.REQUEST_DEBIT,
                        session_id=session_id,
                        balance_after=account.balance,
                        metadata_json={"ai_tool": ai_tool, "request_id": request_id},
                        idempotency_key=idempotency_key,
                    )
                )
                return account.balance

    async def get_credit_state(self, user_id: str) -> CreditState:
        """Return computed request-unit details for UI and API responses."""
        async with self._session_factory() as session:
            balance = await self._balance_for_user(session=session, user_id=user_id)

            free_grant_total_stmt: Select = select(func.coalesce(func.sum(CreditLedgerEntry.delta), 0)).where(
                CreditLedgerEntry.user_id == user_id,
                CreditLedgerEntry.reason == LedgerReason.FREE_GRANT,
            )
            free_grant_total = int((await session.execute(free_grant_total_stmt)).scalar_one())

            request_debit_total_stmt: Select = select(func.coalesce(func.sum(-CreditLedgerEntry.delta), 0)).where(
                CreditLedgerEntry.user_id == user_id,
                CreditLedgerEntry.reason == LedgerReason.REQUEST_DEBIT,
            )
            request_debit_total = int((await session.execute(request_debit_total_stmt)).scalar_one())

            free_remaining = max(free_grant_total - request_debit_total, 0)
            paid_remaining = max(balance - free_remaining, 0)

            stripe_exists = await session.get(StripeCustomer, user_id) is not None

            return CreditState(
                request_units_balance=balance,
                free_request_units_remaining=free_remaining,
                paid_request_units_remaining=paid_remaining,
                can_run_request=balance > 0,
                stripe_customer_exists=stripe_exists,
                request_unit_price_eur=REQUEST_UNIT_PRICE_EUR,
            )

    async def apply_purchase_credits(
        self,
        *,
        user_id: str,
        request_units: int,
        stripe_event_id: str,
        stripe_checkout_session_id: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Grant request units from a paid Stripe checkout event idempotently."""
        async with self._session_factory() as session:
            async with session.begin():
                duplicate_stmt: Select = select(CreditLedgerEntry.id).where(
                    CreditLedgerEntry.idempotency_key == f"stripe:{stripe_event_id}"
                )
                existing = (await session.execute(duplicate_stmt)).scalar_one_or_none()
                if existing is not None:
                    return await self._balance_for_user(session=session, user_id=user_id)

                account = await session.get(CreditAccount, user_id, with_for_update=True)
                if account is None:
                    raise ValueError(f"Credit account not found for user_id={user_id}")

                account.balance += request_units
                session.add(
                    CreditLedgerEntry(
                        user_id=user_id,
                        delta=request_units,
                        reason=LedgerReason.PURCHASE,
                        stripe_event_id=stripe_event_id,
                        stripe_checkout_session_id=stripe_checkout_session_id,
                        balance_after=account.balance,
                        idempotency_key=f"stripe:{stripe_event_id}",
                        metadata_json=metadata or {},
                    )
                )
                return account.balance

    async def _get_user_for_update(self, session: AsyncSession, google_sub: str) -> Optional[BillingUser]:
        stmt: Select = select(BillingUser).where(BillingUser.google_sub == google_sub).with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _balance_for_user(self, session: AsyncSession, user_id: str) -> int:
        account = await session.get(CreditAccount, user_id)
        return 0 if account is None else int(account.balance)

    async def find_user_by_email(self, email: str) -> Optional[BillingUserRef]:
        """Resolve billing user by email (used for webhook metadata fallback)."""
        async with self._session_factory() as session:
            stmt: Select = select(BillingUser).where(BillingUser.email == email)
            user = (await session.execute(stmt)).scalar_one_or_none()
            if user is None:
                return None
            return BillingUserRef(id=user.id, email=user.email)

    async def find_user_by_id(self, user_id: str) -> Optional[BillingUserRef]:
        """Resolve billing user by internal id."""
        async with self._session_factory() as session:
            user = await session.get(BillingUser, user_id)
            if user is None:
                return None
            return BillingUserRef(id=user.id, email=user.email)

    def is_enabled(self) -> bool:
        """Whether billing is enabled by configuration."""
        return os.getenv("BILLING_ENABLED", "false").lower() == "true"

    def pack_to_request_units(self, pack_code: str) -> int:
        """Map pack code to request units."""
        mapping = {
            "CREDITS_5": 25,
            "CREDITS_20": 100,
            "CREDITS_50": 250,
        }
        if pack_code not in mapping:
            raise ValueError(f"Unsupported pack code: {pack_code}")
        return mapping[pack_code]

    def new_checkout_client_reference_id(self, user_id: str) -> str:
        """Generate a unique Stripe client reference ID."""
        return f"billing:{user_id}:{uuid.uuid4()}"
