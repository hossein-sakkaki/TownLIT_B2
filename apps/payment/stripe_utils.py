import stripe
from django.conf import settings
from decimal import Decimal
from apps.payment.models import PaymentDonation

def create_stripe_payment_intent(payment_instance: PaymentDonation):
    stripe.api_key = settings.STRIPE_SECRET_KEY

    if payment_instance.stripe_payment_intent_id:
        try:
            intent = stripe.PaymentIntent.retrieve(payment_instance.stripe_payment_intent_id)
            return intent.client_secret
        except stripe.error.InvalidRequestError:
            pass  # ادامه برای ساخت Intent جدید

    # ساخت یک PaymentIntent جدید
    intent = stripe.PaymentIntent.create(
        amount=int(Decimal(payment_instance.amount) * 100),  
        currency=settings.STRIPE_CURRENCY.lower(),
        metadata={
            "payment_id": str(payment_instance.id),
            "reference_number": payment_instance.reference_number,
            "type": "donation",
        },
        description="TownLIT Donation",
    )

    # ذخیره شناسه PaymentIntent در دیتابیس
    payment_instance.stripe_payment_intent_id = intent.id
    payment_instance.save(update_fields=["stripe_payment_intent_id"])

    return intent.client_secret
