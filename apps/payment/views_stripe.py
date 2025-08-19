import stripe
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction

from apps.payment.models import Payment, PaymentInvoice
from .utils import send_payment_confirmation_email, send_payment_rejection_email
import logging

logger = logging.getLogger(__name__)



@csrf_exempt
def stripe_webhook_view(request):
    # --- 0) Logging + signature presence ---
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET or ""
    logger.info(
        "Stripe WH: hit sig_present=%s payload_len=%s secret_len=%s",
        bool(sig_header), len(payload), len(endpoint_secret),
    )

    # --- 1) Verify signature ---
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        logger.error("Stripe WH: invalid payload: %s", str(e)[:120])
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Stripe WH: signature verify FAILED: %s", str(e)[:120])
        return HttpResponse(status=400)

    event_type = event.get('type', '')
    data_obj = event.get('data', {}).get('object', {}) or {}

    # Helper: extract PaymentIntent id from different event shapes
    def _get_pi_id(e_type: str, obj: dict):
        if e_type.startswith('payment_intent'):
            return obj.get('id')
        # e.g. charge.succeeded ⇒ has "payment_intent"
        return obj.get('payment_intent')

    pi_id = _get_pi_id(event_type, data_obj)
    if not pi_id:
        logger.warning("Stripe WH: no payment_intent id on event %s", event_type)
        return JsonResponse({'status': 'ignored'}, status=200)

    # --- 2) Update DB atomically & idempotently ---
    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(stripe_payment_intent_id=pi_id)
        except Payment.DoesNotExist:
            logger.error("Stripe WH: Payment not found for intent %s", pi_id)
            return HttpResponse(status=404)

        if event_type in ('payment_intent.succeeded', 'charge.succeeded'):
            if payment.payment_status != 'confirmed':
                payment.payment_status = 'confirmed'
                payment.confirm_token = None
                payment.confirm_token_created_at = None
                payment.cancel_token = None
                payment.cancel_token_created_at = None
                payment.save(update_fields=[
                    'payment_status',
                    'confirm_token', 'confirm_token_created_at',
                    'cancel_token', 'cancel_token_created_at',
                ])

                # Invoice (idempotent)
                try:
                    PaymentInvoice.objects.get_or_create(
                        payment=payment,
                        defaults={'issued_date': timezone.now(), 'is_paid': True}
                    )
                except Exception:
                    logger.exception("Stripe WH: failed to create invoice")

                try:
                    ok = send_payment_confirmation_email(payment)
                    if not ok:
                        logger.warning("Stripe WH: confirmation email returned False (%s)", payment.reference_number)
                except Exception:
                    logger.exception("Stripe WH: confirmation email crashed")

        elif event_type in ('payment_intent.payment_failed', 'payment_intent.canceled'):
            new_status = 'canceled' if event_type.endswith('canceled') else 'rejected'
            if payment.payment_status not in ('confirmed', new_status):
                payment.payment_status = new_status
                payment.confirm_token = None
                payment.confirm_token_created_at = None
                payment.cancel_token = None
                payment.cancel_token_created_at = None
                payment.save(update_fields=[
                    'payment_status',
                    'confirm_token', 'confirm_token_created_at',
                    'cancel_token', 'cancel_token_created_at',
                ])
                try:
                    send_payment_rejection_email(payment)
                except Exception:
                    logger.exception("Stripe WH: rejection email crashed")

        else:
            logger.info("Stripe WH: event %s ignored", event_type)

    return JsonResponse({'status': 'ok'}, status=200)
