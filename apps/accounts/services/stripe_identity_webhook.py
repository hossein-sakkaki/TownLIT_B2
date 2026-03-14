# apps/accounts/services/stripe_identity_webhook.py

import stripe
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def verify_stripe_webhook(payload, sig_header):
    """
    Verify Stripe Identity webhook signature.
    """

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_IDENTITY_WEBHOOK_SECRET,
        )

        return event

    except stripe.error.SignatureVerificationError as exc:

        logger.warning(
            "[StripeIdentityWebhook] Invalid signature error=%s",
            exc,
        )

        return None

    except ValueError as exc:

        logger.warning(
            "[StripeIdentityWebhook] Invalid payload error=%s",
            exc,
        )

        return None