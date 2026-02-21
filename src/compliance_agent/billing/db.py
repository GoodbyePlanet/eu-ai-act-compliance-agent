"""Database utilities for billing persistence."""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from compliance_agent.billing.models import Base

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _db_url() -> str:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL environment variable not set.")
    return db_url


def get_billing_engine() -> AsyncEngine:
    """Return a singleton async engine for billing DB access."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(_db_url())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return a singleton async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(bind=get_billing_engine(), expire_on_commit=False)
    return _session_factory


async def init_billing_schema() -> None:
    """Create billing tables if they do not exist."""
    engine = get_billing_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
