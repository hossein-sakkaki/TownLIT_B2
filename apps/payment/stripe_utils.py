import stripe
from decimal import Decimal
from django.conf import settings
from apps.payment.models import PaymentDonation

def create_stripe_payment_intent(payment_instance: PaymentDonation) -> str:
    """
    Creates or updates a PaymentIntent for a donation.
    - Always sets metadata so webhook can match by both PI and our internal PK
    - Persists PaymentIntent ID on our Payment record
    - If an existing PI is still editable, updates amount/metadata to keep them in sync
    """
    stripe.api_key = settings.STRIPE_SECRET_KEY

    amount_cents = int(Decimal(payment_instance.amount) * 100)
    currency = (settings.STRIPE_CURRENCY or "CAD").lower()

    # 1) Try to reuse existing PI if present
    if payment_instance.stripe_payment_intent_id:
        try:
            intent = stripe.PaymentIntent.retrieve(payment_instance.stripe_payment_intent_id)

            # If PI is still in a modifiable state, update amount/metadata/description
            if intent.status in ("requires_payment_method", "requires_confirmation", "requires_action", "processing"):
                # Keep metadata in sync for robust webhook matching
                patch = {
                    "amount": amount_cents,
                    "currency": currency,
                    "description": f"TownLIT Donation {payment_instance.reference_number}",
                    "metadata": {
                        "payment_id": str(payment_instance.id),
                        "reference_number": payment_instance.reference_number,
                        "type": "donation",
                    },
                }
                intent = stripe.PaymentIntent.modify(intent.id, **patch)

            # Return client secret irrespective of status; the front-end will handle required actions
            return intent.client_secret

        except stripe.error.InvalidRequestError:
            # Fall through to create a new PI if the old one was deleted/invalid
            pass

    # 2) Create a fresh PI
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        description=f"TownLIT Donation {payment_instance.reference_number}",
        metadata={
            "payment_id": str(payment_instance.id),
            "reference_number": payment_instance.reference_number,
            "type": "donation",
        },
        # Enable Stripe to choose the best payment method unless you use a fixed one
        automatic_payment_methods={"enabled": True},
    )

    # 3) Persist PI id (so webhook can match by PI)
    if payment_instance.stripe_payment_intent_id != intent.id:
        payment_instance.stripe_payment_intent_id = intent.id
        payment_instance.save(update_fields=["stripe_payment_intent_id"])

    return intent.client_secret
