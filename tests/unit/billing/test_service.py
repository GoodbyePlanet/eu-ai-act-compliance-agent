import asyncio
from collections.abc import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from compliance_agent.billing.models import Base, CreditLedgerEntry, LedgerReason
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


def test_ensure_user_grants_free_request_units_only_once(billing_service: BillingService) -> None:
    """First user bootstrap grants 5 request units and does not repeat."""

    async def _run() -> None:
        created = await billing_service.ensure_user("sub-1", "user@example.com")
        await billing_service.ensure_user("sub-1", "user-updated@example.com")

        state = await billing_service.get_credit_state(created.id)
        assert state.request_units_balance == 5
        assert state.free_request_units_remaining == 5
        assert state.paid_request_units_remaining == 0
        assert state.can_run_request is True
        assert state.request_unit_price_eur == 0.2

        async with billing_service._session_factory() as session:  # type: ignore[attr-defined]
            stmt = select(CreditLedgerEntry).where(
                CreditLedgerEntry.user_id == created.id,
                CreditLedgerEntry.reason == LedgerReason.FREE_GRANT,
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].delta == 5

    asyncio.run(_run())


def test_consume_credit_for_request_debits_per_request_and_is_idempotent(
    billing_service: BillingService,
) -> None:
    """A request debit consumes one unit and duplicate request_id does not double charge."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-2", "user2@example.com")

        balance_after_first = await billing_service.consume_credit_for_request(
            user_id=user.id,
            request_id="req-1",
            session_id="session-1",
            ai_tool="Notion AI",
        )
        balance_after_duplicate = await billing_service.consume_credit_for_request(
            user_id=user.id,
            request_id="req-1",
            session_id="session-1",
            ai_tool="Notion AI",
        )

        assert balance_after_first == 4
        assert balance_after_duplicate == 4

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


def test_consume_credit_for_request_raises_when_balance_is_empty(billing_service: BillingService) -> None:
    """User cannot submit more requests than available free request units."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-3", "user3@example.com")

        for idx in range(5):
            await billing_service.consume_credit_for_request(
                user_id=user.id,
                request_id=f"req-{idx}",
                session_id=f"session-{idx}",
                ai_tool="ChatGPT",
            )

        with pytest.raises(InsufficientCreditsError):
            await billing_service.consume_credit_for_request(
                user_id=user.id,
                request_id="req-over-limit",
                session_id="session-over-limit",
                ai_tool="ChatGPT",
            )

        state = await billing_service.get_credit_state(user.id)
        assert state.request_units_balance == 0
        assert state.can_run_request is False

    asyncio.run(_run())


def test_apply_purchase_credits_is_idempotent_and_tracks_paid_balance(
    billing_service: BillingService,
) -> None:
    """Applying the same Stripe event twice must only grant once."""

    async def _run() -> None:
        user = await billing_service.ensure_user("sub-4", "user4@example.com")

        for idx in range(3):
            await billing_service.consume_credit_for_request(
                user_id=user.id,
                request_id=f"req-spend-{idx}",
                session_id="session-paid",
                ai_tool="Claude",
            )

        balance_after_first = await billing_service.apply_purchase_credits(
            user_id=user.id,
            request_units=10,
            stripe_event_id="evt_1",
            stripe_checkout_session_id="cs_1",
            metadata={"source": "test"},
        )
        balance_after_duplicate = await billing_service.apply_purchase_credits(
            user_id=user.id,
            request_units=10,
            stripe_event_id="evt_1",
            stripe_checkout_session_id="cs_1",
            metadata={"source": "test"},
        )

        assert balance_after_first == 12
        assert balance_after_duplicate == 12

        state = await billing_service.get_credit_state(user.id)
        assert state.request_units_balance == 12
        assert state.free_request_units_remaining == 2
        assert state.paid_request_units_remaining == 10

        async with billing_service._session_factory() as session:  # type: ignore[attr-defined]
            stmt = select(CreditLedgerEntry).where(
                CreditLedgerEntry.user_id == user.id,
                CreditLedgerEntry.reason == LedgerReason.PURCHASE,
            )
            rows = (await session.execute(stmt)).scalars().all()
            assert len(rows) == 1
            assert rows[0].delta == 10
            assert rows[0].idempotency_key == "stripe:evt_1"

    asyncio.run(_run())


def test_pack_to_request_units_returns_expected_values(billing_service: BillingService) -> None:
    """Supported Stripe packs should map to request-unit quantities."""
    assert billing_service.pack_to_request_units("CREDITS_5") == 25
    assert billing_service.pack_to_request_units("CREDITS_20") == 100
    assert billing_service.pack_to_request_units("CREDITS_50") == 250
