"""Stripe integration helpers for checkout, portal, and webhook processing."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Tuple

from sqlalchemy import select

from compliance_agent.billing.db import get_session_factory
from compliance_agent.billing.models import StripeCheckoutSession, StripeCustomer, StripeWebhookEvent
from compliance_agent.billing.service import BillingService

logger = logging.getLogger(__name__)

try:
    import stripe
except ImportError:  # pragma: no cover - exercised in environments without stripe installed.
    stripe = None


class StripeService:
    """Encapsulates Stripe SDK calls and local persistence for billing."""

    def __init__(self, billing_service: BillingService):
        self._billing_service = billing_service
        api_key = os.getenv("STRIPE_SECRET_KEY")
        if stripe and api_key:
            stripe.api_key = api_key
        self._session_factory = get_session_factory()
        self._currency = os.getenv("BILLING_CURRENCY", "eur")
        self._success_url = os.getenv("STRIPE_SUCCESS_URL", "http://localhost:8501")
        self._cancel_url = os.getenv("STRIPE_CANCEL_URL", "http://localhost:8501")

    @staticmethod
    def _require_stripe() -> None:
        if stripe is None:
            raise RuntimeError("Stripe SDK is not installed. Install `stripe` package to enable payments.")

    def _pack_price_config(self, pack_code: str) -> str:
        mapping = {
            "CREDITS_5": os.getenv("STRIPE_PRICE_ID_CREDITS_5"),
            "CREDITS_20": os.getenv("STRIPE_PRICE_ID_CREDITS_20"),
            "CREDITS_50": os.getenv("STRIPE_PRICE_ID_CREDITS_50"),
        }
        price_config = mapping.get(pack_code)
        if not price_config:
            raise ValueError(f"Price ID not configured for pack code: {pack_code}")
        return price_config.strip()

    def _line_item_for_pack(self, pack_code: str, request_units: int) -> Dict[str, Any]:
        """Build a valid Stripe line item from configured pack pricing."""
        price_config = self._pack_price_config(pack_code=pack_code)

        if price_config.startswith("price_"):
            return {"price": price_config, "quantity": 1}

        if re.fullmatch(r"\d+", price_config):
            amount_minor = int((Decimal(price_config) * Decimal("100")).to_integral_value())
            if amount_minor <= 0:
                raise ValueError(f"Configured amount must be positive for pack code: {pack_code}")
            return {
                "price_data": {
                    "currency": self._currency,
                    "unit_amount": amount_minor,
                    "product_data": {"name": f"Compliance Credits ({request_units} requests)"},
                },
                "quantity": 1,
            }

        if re.fullmatch(r"\d+(\.\d{1,2})?", price_config):
            try:
                amount_minor = int((Decimal(price_config) * Decimal("100")).to_integral_value())
            except InvalidOperation as exc:
                raise ValueError(f"Invalid configured amount for pack code: {pack_code}") from exc

            if amount_minor <= 0:
                raise ValueError(f"Configured amount must be positive for pack code: {pack_code}")
            return {
                "price_data": {
                    "currency": self._currency,
                    "unit_amount": amount_minor,
                    "product_data": {"name": f"Compliance Credits ({request_units} requests)"},
                },
                "quantity": 1,
            }

        raise ValueError(
            f"Invalid Stripe price configuration for {pack_code}. Expected Stripe Price ID (price_...) "
            f"or numeric amount."
        )

    async def get_or_create_customer(self, *, user_id: str, email: str) -> str:
        """Get existing Stripe customer id or create one and persist mapping."""
        self._require_stripe()
        async with self._session_factory() as session:
            existing = await session.get(StripeCustomer, user_id)
            if existing is not None:
                return existing.stripe_customer_id

        customer = stripe.Customer.create(email=email, metadata={"user_id": user_id})

        async with self._session_factory() as session:
            async with session.begin():
                existing = await session.get(StripeCustomer, user_id)
                if existing is not None:
                    return existing.stripe_customer_id
                session.add(StripeCustomer(user_id=user_id, stripe_customer_id=customer["id"]))
        return customer["id"]

    async def create_checkout_session(self, *, user_id: str, email: str, pack_code: str) -> Dict[str, Any]:
        """Create a stripe checkout session for a configured credit pack."""
        logger.info("Creating Stripe checkout session for user_id=%s pack_code=%s", user_id, pack_code)
        self._require_stripe()

        request_units = self._billing_service.pack_to_request_units(pack_code)
        customer_id = await self.get_or_create_customer(user_id=user_id, email=email)
        line_item = self._line_item_for_pack(pack_code=pack_code, request_units=request_units)

        checkout = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[line_item],
            billing_address_collection="required",
            customer_update={"address": "auto", "name": "auto"},
            success_url=self._success_url,
            cancel_url=self._cancel_url,
            automatic_tax={"enabled": True},
            client_reference_id=self._billing_service.new_checkout_client_reference_id(user_id=user_id),
            metadata={
                "user_id": user_id,
                "pack_code": pack_code,
                "request_units": str(request_units),
                "email": email,
            },
        )

        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    StripeCheckoutSession(
                        user_id=user_id,
                        pack_code=pack_code,
                        request_units_to_grant=request_units,
                        amount_minor=int(checkout["amount_total"] or 0),
                        currency=(checkout.get("currency") or self._currency),
                        stripe_checkout_session_id=checkout["id"],
                        status=checkout["status"] or "created",
                    )
                )

        logger.info(f"Created Stripe checkout session for a user: %s", user_id, extra={"checkout_id": checkout["id"]})
        return {"checkout_url": checkout["url"], "checkout_session_id": checkout["id"]}

    async def create_portal_session(self, *, user_id: str, email: str) -> Dict[str, Any]:
        """Create stripe billing portal session URL."""
        logger.info("Creating Stripe billing portal session for user_id=%s", user_id)
        self._require_stripe()
        customer_id = await self.get_or_create_customer(user_id=user_id, email=email)
        portal = stripe.billing_portal.Session.create(customer=customer_id, return_url=self._success_url)

        return {"portal_url": portal["url"]}

    def construct_event(self, payload: bytes, stripe_signature: str) -> Dict[str, Any]:
        """Verify and construct Stripe webhook event."""
        self._require_stripe()
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")
        event = stripe.Webhook.construct_event(payload=payload, sig_header=stripe_signature, secret=webhook_secret)
        return dict(event)

    async def process_checkout_completed(self, *, event: Dict[str, Any], raw_payload: bytes) -> Tuple[bool, str]:
        """Process completed checkout and grant credits idempotently."""
        logger.info("Processing Stripe checkout completed event...")
        event_id = event["id"]
        event_type = event["type"]
        payload_hash = hashlib.sha256(raw_payload).hexdigest()

        async with self._session_factory() as session:
            existing = await session.get(StripeWebhookEvent, event_id)
            if existing is not None:
                return False, "already_processed"

        data_obj = event.get("data", {}).get("object", {})
        metadata = data_obj.get("metadata", {}) or {}
        user_id = metadata.get("user_id")
        request_units_raw = metadata.get("request_units", "0")
        checkout_session_id = data_obj.get("id", "")

        if not user_id:
            email = metadata.get("email")
            if email:
                user_ref = await self._billing_service.find_user_by_email(email)
                user_id = user_ref.id if user_ref else None

        if not user_id:
            raise ValueError("Could not resolve user_id from Stripe webhook metadata")

        request_units = int(request_units_raw)
        await self._billing_service.apply_purchase_credits(
            user_id=user_id,
            request_units=request_units,
            stripe_event_id=event_id,
            stripe_checkout_session_id=checkout_session_id,
            metadata={"event_type": event_type},
        )

        async with self._session_factory() as session:
            async with session.begin():
                session.add(
                    StripeWebhookEvent(
                        stripe_event_id=event_id,
                        event_type=event_type,
                        payload_hash=payload_hash,
                    )
                )

                stmt = select(StripeCheckoutSession).where(
                    StripeCheckoutSession.stripe_checkout_session_id == checkout_session_id
                )
                checkout_record = (await session.execute(stmt)).scalar_one_or_none()
                if checkout_record is not None:
                    checkout_record.status = "completed"

        logger.info(
            "Stripe checkout processed: event_id=%s user_id=%s request_units=%s",
            event_id,
            user_id,
            request_units,
        )
        return True, "processed"
