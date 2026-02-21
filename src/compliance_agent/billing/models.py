"""SQLAlchemy models for billing and credits."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for billing models."""


class LedgerReason(str, enum.Enum):
    """Reason enum for credit ledger entries."""

    FREE_GRANT = "FREE_GRANT"
    PURCHASE = "PURCHASE"
    SESSION_DEBIT = "SESSION_DEBIT"
    ADJUSTMENT = "ADJUSTMENT"
    REFUND = "REFUND"


class BillingSessionStatus(str, enum.Enum):
    """Status for billing-tracked assessment sessions."""

    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class BillingUser(Base):
    """Application billing user identity."""

    __tablename__ = "billing_users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    free_credits_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    account: Mapped["CreditAccount"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")


class CreditAccount(Base):
    """Current credit balance for a user."""

    __tablename__ = "credit_accounts"

    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), primary_key=True)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    user: Mapped[BillingUser] = relationship(back_populates="account")


class CreditLedgerEntry(Base):
    """Immutable ledger for all credit mutations."""

    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[LedgerReason] = mapped_column(Enum(LedgerReason), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_credit_ledger_user_reason", "user_id", "reason"),
    )


class AssessmentBillingSession(Base):
    """Maps one assessment session to one consumed credit and canonical tool."""

    __tablename__ = "assessment_billing_sessions"

    session_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), index=True)
    canonical_tool_name: Mapped[str] = mapped_column(Text)
    canonical_tool_fingerprint: Mapped[str] = mapped_column(String(255), index=True)
    credit_ledger_debit_id: Mapped[str] = mapped_column(String(64), ForeignKey("credit_ledger.id", ondelete="RESTRICT"))
    status: Mapped[BillingSessionStatus] = mapped_column(Enum(BillingSessionStatus), default=BillingSessionStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class StripeCustomer(Base):
    """Stripe customer reference by internal user."""

    __tablename__ = "stripe_customers"

    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), primary_key=True)
    stripe_customer_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)


class StripeCheckoutSession(Base):
    """Tracks checkout sessions created for credit purchases."""

    __tablename__ = "stripe_checkout_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), index=True)
    pack_code: Mapped[str] = mapped_column(String(64), index=True)
    credits_to_grant: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    stripe_checkout_session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="created")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class StripeWebhookEvent(Base):
    """Idempotency guard for processed stripe webhooks."""

    __tablename__ = "stripe_webhook_events"

    stripe_event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("stripe_event_id", name="uq_stripe_event_id"),)
