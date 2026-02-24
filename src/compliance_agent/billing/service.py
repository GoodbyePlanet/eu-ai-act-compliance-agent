"""Business logic for daily request quota enforcement."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from compliance_agent.billing.db import get_session_factory
from compliance_agent.billing.models import BillingUser, CreditLedgerEntry, LedgerReason

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when a user has no daily credits left."""


@dataclass(frozen=True)
class DailyCreditState:
    """Current user daily quota state."""

    daily_limit: int
    used_today: int
    credits_left_today: int
    can_run_request: bool
    resets_at_utc: str


@dataclass(frozen=True)
class BillingUserRef:
    """Minimal internal user reference for billing flows."""

    id: str
    email: str


class BillingService:
    """Service for all daily quota operations."""

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]] = None):
        self._session_factory = session_factory or get_session_factory()
        self._daily_limit = int(os.getenv("DAILY_FREE_CREDITS", "20"))

    async def ensure_user(self, google_sub: str, email: str) -> BillingUserRef:
        """Create or retrieve user identity used for quota tracking."""
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

            return BillingUserRef(id=user.id, email=user.email)

    async def consume_daily_credit_for_request(
        self,
        *,
        user_id: str,
        request_id: str,
        session_id: Optional[str],
        ai_tool: str,
    ) -> int:
        """Atomically consume one daily credit for each accepted assessment request."""
        day_start, next_day_start = self._utc_day_bounds()
        idempotency_key = f"request-debit:{user_id}:{request_id}"

        async with self._session_factory() as session:
            async with session.begin():
                existing_stmt: Select = select(CreditLedgerEntry.id).where(
                    CreditLedgerEntry.idempotency_key == idempotency_key
                )
                existing = (await session.execute(existing_stmt)).scalar_one_or_none()
                if existing is not None:
                    used_today = await self._used_today(
                        session=session,
                        user_id=user_id,
                        day_start=day_start,
                        next_day_start=next_day_start,
                    )
                    return max(self._daily_limit - used_today, 0)

                used_today = await self._used_today(
                    session=session,
                    user_id=user_id,
                    day_start=day_start,
                    next_day_start=next_day_start,
                )
                if used_today >= self._daily_limit:
                    reset_at = next_day_start.isoformat()
                    raise InsufficientCreditsError(
                        f"Daily limit reached ({self._daily_limit}/{self._daily_limit}). "
                        f"Try again after reset at {reset_at}."
                    )

                remaining_after = self._daily_limit - (used_today + 1)
                session.add(
                    CreditLedgerEntry(
                        user_id=user_id,
                        delta=-1,
                        reason=LedgerReason.REQUEST_DEBIT,
                        session_id=session_id,
                        balance_after=remaining_after,
                        metadata_json={"ai_tool": ai_tool, "request_id": request_id},
                        idempotency_key=idempotency_key,
                    )
                )

                return remaining_after

    async def get_daily_credit_state(self, user_id: str) -> DailyCreditState:
        """Return daily quota details for UI and API responses."""
        day_start, next_day_start = self._utc_day_bounds()
        async with self._session_factory() as session:
            used_today = await self._used_today(
                session=session,
                user_id=user_id,
                day_start=day_start,
                next_day_start=next_day_start,
            )

        credits_left_today = max(self._daily_limit - used_today, 0)
        return DailyCreditState(
            daily_limit=self._daily_limit,
            used_today=used_today,
            credits_left_today=credits_left_today,
            can_run_request=credits_left_today > 0,
            resets_at_utc=next_day_start.isoformat(),
        )

    async def _used_today(
        self,
        *,
        session: AsyncSession,
        user_id: str,
        day_start: datetime,
        next_day_start: datetime,
    ) -> int:
        stmt: Select = select(func.coalesce(func.count(CreditLedgerEntry.id), 0)).where(
            CreditLedgerEntry.user_id == user_id,
            CreditLedgerEntry.reason == LedgerReason.REQUEST_DEBIT,
            CreditLedgerEntry.created_at >= day_start,
            CreditLedgerEntry.created_at < next_day_start,
        )
        return int((await session.execute(stmt)).scalar_one())

    async def _get_user_for_update(self, session: AsyncSession, google_sub: str) -> Optional[BillingUser]:
        stmt: Select = select(BillingUser).where(BillingUser.google_sub == google_sub).with_for_update()
        return (await session.execute(stmt)).scalar_one_or_none()

    async def find_user_by_id(self, user_id: str) -> Optional[BillingUserRef]:
        """Resolve billing user by internal id."""
        async with self._session_factory() as session:
            user = await session.get(BillingUser, user_id)
            if user is None:
                return None
            return BillingUserRef(id=user.id, email=user.email)

    def is_enabled(self) -> bool:
        """Whether daily quota enforcement is enabled by configuration."""
        return os.getenv("BILLING_ENABLED", "true").lower() == "true"

    def _utc_day_bounds(self) -> tuple[datetime, datetime]:
        now_utc = datetime.now(timezone.utc)
        day_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        return day_start, day_start + timedelta(days=1)
