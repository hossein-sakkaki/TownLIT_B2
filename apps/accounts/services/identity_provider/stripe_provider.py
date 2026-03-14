# apps/accounts/services/identity_provider/stripe_provider.py

import logging
import stripe
from django.conf import settings

from .base import BaseIdentityProvider

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeIdentityProvider(BaseIdentityProvider):
    """
    Stripe Identity implementation.
    """

    def create_session(self, user, success_url=None, failure_url=None) -> dict:
        """
        Create Stripe Identity verification session.
        """

        return_url = success_url or settings.IDENTITY_RETURN_URL

        try:
            session = stripe.identity.VerificationSession.create(
                type="document",
                return_url=return_url,
                metadata={
                    "user_id": str(user.id),
                    "email": user.email,
                },
                options={
                    "document": {
                        "require_id_number": False,
                        "require_live_capture": True,
                        "require_matching_selfie": True,
                    }
                },
            )

            logger.info(
                "[StripeIdentity] Session created user_id=%s session_id=%s status=%s",
                user.id,
                session.id,
                session.status,
            )

            return {
                "verification": {
                    "id": session.id,
                    "url": getattr(session, "url", None),
                    "status": session.status,
                    "raw": dict(session),
                }
            }

        except stripe.error.StripeError as exc:
            logger.exception(
                "[StripeIdentity] Stripe error user_id=%s error=%s",
                user.id,
                exc,
            )
            raise RuntimeError("Stripe identity verification failed.")

    def retrieve_session(self, session_id: str) -> dict:
        """
        Retrieve Stripe Identity verification session and normalize it.
        """

        try:
            session = stripe.identity.VerificationSession.retrieve(session_id)

            last_error = session.get("last_error")
            reason = None

            if isinstance(last_error, dict):
                reason = last_error.get("reason") or last_error.get("code")
            elif last_error:
                reason = str(last_error)

            return {
                "id": session.get("id"),
                "status": session.get("status"),
                "reason": reason,
                "risk": [],
                "raw": dict(session),
            }

        except stripe.error.InvalidRequestError:
            logger.warning(
                "[StripeIdentity] Session not found session_id=%s",
                session_id,
            )
            return {
                "id": session_id,
                "status": "not_found",
                "reason": "Verification session not found on Stripe.",
                "risk": [],
                "raw": {},
            }

        except stripe.error.StripeError as exc:
            logger.exception(
                "[StripeIdentity] Failed to retrieve session session_id=%s error=%s",
                session_id,
                exc,
            )
            raise RuntimeError("Failed to retrieve Stripe identity session.")

    def verify_webhook(self, raw_body: bytes, signature_header: str):
        """
        Verify Stripe webhook signature.
        """

        if not signature_header:
            return None

        try:
            event = stripe.Webhook.construct_event(
                raw_body,
                signature_header,
                settings.STRIPE_IDENTITY_WEBHOOK_SECRET,
            )
            return event

        except stripe.error.SignatureVerificationError:
            logger.warning("[StripeIdentity] Invalid webhook signature")
            return None

        except Exception:
            logger.exception("[StripeIdentity] Failed to verify webhook")
            return None

    def parse_webhook(self, event) -> dict:
        """
        Normalize Stripe Identity webhook payload.
        """

        event_type = event["type"]
        session = event["data"]["object"]

        status = session.get("status")

        if event_type == "identity.verification_session.verified":
            status = "verified"
        elif event_type == "identity.verification_session.requires_input":
            status = "requires_input"
        elif event_type == "identity.verification_session.canceled":
            status = "canceled"

        last_error = session.get("last_error")
        reason = None

        if isinstance(last_error, dict):
            reason = last_error.get("reason") or last_error.get("code")
        elif last_error:
            reason = str(last_error)

        return {
            "session_id": session.get("id"),
            "status": status,
            "reason": reason,
            "risk": [],
            "raw": event,
        }