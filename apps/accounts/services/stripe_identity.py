# apps/accounts/services/stripe_identity.py

import stripe
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def create_stripe_verification_session(user, success_url=None, failure_url=None):
    """
    Create Stripe Identity verification session.
    """

    try:

        session = stripe.identity.VerificationSession.create(
            type="document",
            metadata={
                "user_id": str(user.id),
                "email": user.email,
            },
            return_url=success_url or settings.IDENTITY_RETURN_URL,
        )

        logger.info(
            "[StripeIdentity] Session created user_id=%s session_id=%s",
            user.id,
            session.id,
        )

        return {
            "verification": {
                "id": session.id,
                "url": session.url,
                "status": session.status,
                "raw": session,
            }
        }

    except stripe.error.StripeError as exc:

        logger.exception(
            "[StripeIdentity] Stripe error user_id=%s error=%s",
            user.id,
            exc,
        )

        raise RuntimeError("Stripe identity verification failed.")