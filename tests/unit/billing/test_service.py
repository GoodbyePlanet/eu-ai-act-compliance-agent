import asyncio
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from compliance_agent.billing.models import Base, BillingUser, CreditLedgerEntry, LedgerReason
from compliance_agent.billing.service import BillingService, InsufficientCreditsError


@pytest.fixture
def billing_service() -> Generator[BillingService, None, None]:
    """Create a billing service backed by an isolated in-memory DB."""
    engine: AsyncEngine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())

    service = BillingService(session_factory=session_factory)

    try:
        yield service
    finally:
        asyncio.run(engine.dispose())


def test_ensure_user_creates_identity_only_once(billing_service: BillingService) -> None:
    """First user bootstrap should create user and subsequent calls should reuse it."""

    async def _run() -> None:
        created = await billing_service.ensure_user("sub-1", "user@example.com")
        second = await billing_service.ensure_user("sub-1", "user-updated@example.com")

        assert created.id == second.id
        assert second.email == "user-updated@example.com"

    asyncio.run(_run())


def test_consume_daily_credit_debits_per_request_and_is_idempotent(
    billing_service: BillingService,
) -> None:
    """A request debit consumes one unit and duplicate request_id does not double charge."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-2", "user2@example.com")

        left_after_first = await billing_service.consume_daily_credit_for_request(
            user_id=user.id,
            request_id="req-1",
            session_id="session-1",
            ai_tool="Notion AI",
        )
        left_after_duplicate = await billing_service.consume_daily_credit_for_request(
            user_id=user.id,
            request_id="req-1",
            session_id="session-1",
            ai_tool="Notion AI",
        )

        assert left_after_first == 19
        assert left_after_duplicate == 19

        async with billing_service._session_factory() as session:  # type: ignore[attr-defined]
            stmt = select(CreditLedgerEntry).where(
                CreditLedgerEntry.user_id == user.id,
                CreditLedgerEntry.reason == LedgerReason.REQUEST_DEBIT,
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].delta == -1
            assert rows[0].session_id == "session-1"
            assert rows[0].idempotency_key == f"request-debit:{user.id}:req-1"

    asyncio.run(_run())


def test_consume_daily_credit_raises_when_day_limit_is_reached(billing_service: BillingService) -> None:
    """User cannot submit more than 20 requests in the same UTC day."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-3", "user3@example.com")

        for idx in range(20):
            await billing_service.consume_daily_credit_for_request(
                user_id=user.id,
                request_id=f"req-{idx}",
                session_id=f"session-{idx}",
                ai_tool="ChatGPT",
            )

        with pytest.raises(InsufficientCreditsError):
            await billing_service.consume_daily_credit_for_request(
                user_id=user.id,
                request_id="req-over-limit",
                session_id="session-over-limit",
                ai_tool="ChatGPT",
            )

        state = await billing_service.get_daily_credit_state(user.id)
        assert state.credits_left_today == 0
        assert state.can_run_request is False
        assert state.used_today == 20

    asyncio.run(_run())


def test_daily_state_ignores_previous_day_entries(billing_service: BillingService) -> None:
    """Credits consumed before current UTC day must not affect today's quota."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-4", "user4@example.com")

        async with billing_service._session_factory() as session:  # type: ignore[attr-defined]
            db_user = await session.get(BillingUser, user.id)
            assert db_user is not None
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            session.add(
                CreditLedgerEntry(
                    user_id=db_user.id,
                    delta=-1,
                    reason=LedgerReason.REQUEST_DEBIT,
                    session_id="yesterday",
                    idempotency_key="request-debit:yesterday",
                    balance_after=0,
                    metadata_json={"ai_tool": "Old Tool"},
                    created_at=yesterday,
                )
            )
            await session.commit()

        state = await billing_service.get_daily_credit_state(user.id)
        assert state.used_today == 0
        assert state.credits_left_today == 20

    asyncio.run(_run())
