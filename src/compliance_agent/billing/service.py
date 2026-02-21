"""Business logic for credits, account bootstrap, and session charging."""

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
    AssessmentBillingSession,
    BillingSessionStatus,
    BillingUser,
    CreditAccount,
    CreditLedgerEntry,
    LedgerReason,
    StripeCustomer,
)
from compliance_agent.billing.tool_lock import canonicalize_tool_name, validate_follow_up_tool_lock

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when a user has no credits left for a new session."""


class NewToolInFollowUpError(Exception):
    """Raised when follow-up appears to switch tool in existing paid session."""


@dataclass(frozen=True)
class CreditState:
    """Current user credit balances."""

    credits_balance: int
    free_credits_remaining: int
    paid_credits_remaining: int
    can_start_new_session: bool
    stripe_customer_exists: bool


@dataclass(frozen=True)
class BillingUserRef:
    """Minimal internal user reference for billing flows."""

    id: str
    email: str


class BillingService:
    """Service for all billing and credits operations."""

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        self._session_factory = session_factory or get_session_factory()
        self._free_credits = int(os.getenv("FREE_CREDITS_ON_SIGNUP", "5"))

    async def ensure_user(self, google_sub: str, email: str) -> BillingUserRef:
        """Create or retrieve user/account and grant one-time free credits."""
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
                    account.balance += self._free_credits
                    user.free_credits_granted_at = datetime.now(timezone.utc)
                    session.add(
                        CreditLedgerEntry(
                            user_id=user.id,
                            delta=self._free_credits,
                            reason=LedgerReason.FREE_GRANT,
                            balance_after=account.balance,
                            metadata_json={"source": "signup"},
                            idempotency_key=f"free-grant:{user.id}",
                        )
                    )
            return BillingUserRef(id=user.id, email=user.email)

    async def consume_credit_for_new_session(self, user_id: str, session_id: str, ai_tool: str) -> int:
        """Atomically consume one credit and lock canonical tool for a new session."""
        fingerprint = canonicalize_tool_name(ai_tool)

        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.get(AssessmentBillingSession, session_id, with_for_update=True)
                if existing is not None:
                    return await self._balance_for_user(session=session, user_id=user_id)

                account = await session.get(CreditAccount, user_id, with_for_update=True)
                if account is None or account.balance < 1:
                    raise InsufficientCreditsError("No credits available for a new assessment session")

                account.balance -= 1
                debit_entry = CreditLedgerEntry(
                    user_id=user_id,
                    delta=-1,
                    reason=LedgerReason.SESSION_DEBIT,
                    session_id=session_id,
                    balance_after=account.balance,
                    metadata_json={"ai_tool": ai_tool},
                    idempotency_key=f"session-debit:{user_id}:{session_id}",
                )
                session.add(debit_entry)
                await session.flush()

                session.add(
                    AssessmentBillingSession(
                        session_id=session_id,
                        user_id=user_id,
                        canonical_tool_name=ai_tool,
                        canonical_tool_fingerprint=fingerprint,
                        credit_ledger_debit_id=debit_entry.id,
                        status=BillingSessionStatus.ACTIVE,
                    )
                )

                return account.balance

    async def validate_follow_up_or_raise(self, user_id: str, session_id: str, message: str) -> None:
        """Ensure follow-up stays scoped to canonical tool in the charged session."""
        async with self._session_factory() as session:
            billing_session = await session.get(AssessmentBillingSession, session_id)
            if billing_session is None:
                # Legacy session without billing record; allow for compatibility.
                return

            if billing_session.user_id != user_id:
                raise NewToolInFollowUpError("Session ownership mismatch for billing scope")

            result = validate_follow_up_tool_lock(message=message, canonical_tool=billing_session.canonical_tool_name)
            if not result.allowed:
                raise NewToolInFollowUpError(result.reason)

    async def get_credit_state(self, user_id: str) -> CreditState:
        """Return computed balance details for UI and API responses."""
        async with self._session_factory() as session:
            balance = await self._balance_for_user(session=session, user_id=user_id)

            free_grant_total_stmt: Select = select(func.coalesce(func.sum(CreditLedgerEntry.delta), 0)).where(
                CreditLedgerEntry.user_id == user_id,
                CreditLedgerEntry.reason == LedgerReason.FREE_GRANT,
            )
            free_grant_total = int((await session.execute(free_grant_total_stmt)).scalar_one())

            debit_total_stmt: Select = select(func.coalesce(func.sum(-CreditLedgerEntry.delta), 0)).where(
                CreditLedgerEntry.user_id == user_id,
                CreditLedgerEntry.reason == LedgerReason.SESSION_DEBIT,
            )
            debit_total = int((await session.execute(debit_total_stmt)).scalar_one())

            free_remaining = max(free_grant_total - debit_total, 0)
            paid_remaining = max(balance - free_remaining, 0)

            stripe_exists = await session.get(StripeCustomer, user_id) is not None

            return CreditState(
                credits_balance=balance,
                free_credits_remaining=free_remaining,
                paid_credits_remaining=paid_remaining,
                can_start_new_session=balance > 0,
                stripe_customer_exists=stripe_exists,
            )

    async def apply_purchase_credits(
        self,
        *,
        user_id: str,
        credits: int,
        stripe_event_id: str,
        stripe_checkout_session_id: str,
        metadata: Optional[dict] = None,
    ) -> int:
        """Grant credits from a paid Stripe checkout event idempotently."""
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

                account.balance += credits
                session.add(
                    CreditLedgerEntry(
                        user_id=user_id,
                        delta=credits,
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

    def pack_to_credits(self, pack_code: str) -> int:
        """Map pack code to credits."""
        mapping = {
            "CREDITS_5": 5,
            "CREDITS_20": 20,
            "CREDITS_50": 50,
        }
        if pack_code not in mapping:
            raise ValueError(f"Unsupported pack code: {pack_code}")
        return mapping[pack_code]

    def new_checkout_client_reference_id(self, user_id: str) -> str:
        """Generate a unique Stripe client reference ID."""
        return f"billing:{user_id}:{uuid.uuid4()}"
