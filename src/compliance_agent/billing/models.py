"""SQLAlchemy models for daily quota accounting."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for billing models."""


class LedgerReason(str, enum.Enum):
    """Reason enum for daily quota ledger entries."""

    REQUEST_DEBIT = "REQUEST_DEBIT"
    ADJUSTMENT = "ADJUSTMENT"


class BillingUser(Base):
    """Application user identity used by quota service."""

    __tablename__ = "billing_users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    ledger_entries: Mapped[list["CreditLedgerEntry"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class CreditLedgerEntry(Base):
    """Immutable ledger for request debits and manual adjustments."""

    __tablename__ = "credit_ledger"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("billing_users.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[LedgerReason] = mapped_column(Enum(LedgerReason), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_json: Mapped[dict] = mapped_column(MutableDict.as_mutable(JSON), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    user: Mapped[BillingUser] = relationship(back_populates="ledger_entries")

    __table_args__ = (Index("ix_credit_ledger_user_reason", "user_id", "reason"),)
