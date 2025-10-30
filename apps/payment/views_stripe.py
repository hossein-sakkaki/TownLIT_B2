import stripe
import json
import logging
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction

from apps.payment.models import Payment, PaymentInvoice
from .utils import send_payment_confirmation_email, send_payment_rejection_email

logger = logging.getLogger(__name__)


@csrf_exempt
def stripe_webhook_view(request):
    """
    Robust Stripe webhook:
    - Verifies signature
    - Matches payment by PaymentIntent ID or metadata.payment_id
    - Handles PI, Charge, and Checkout events
    - Idempotent state transitions and invoice creation
    - Always ACKs 200 when record not found to avoid infinite retries
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET or ""

    logger.info(
        "Stripe WH: hit sig_present=%s payload_len=%s secret_len=%s",
        bool(sig_header), len(payload), len(endpoint_secret),
    )

    # 1) Verify signature early; don't parse JSON before verification
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        logger.error("Stripe WH: invalid payload: %s", str(e)[:200])
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        logger.error("Stripe WH: signature verify FAILED: %s", str(e)[:200])
        return HttpResponse(status=400)

    event_type = event.get('type', '')
    data_obj = event.get('data', {}).get('object', {}) or {}

    # 2) Extract PaymentIntent id across shapes
    def _get_pi_id(e_type: str, obj: dict):
        # payment_intent.* events carry the PI as the object itself
        if e_type.startswith('payment_intent'):
            return obj.get('id')
        # charge.succeeded carries the PI under "payment_intent"
        return obj.get('payment_intent')

    pi_id = _get_pi_id(event_type, data_obj)

    # Checkout Session may carry the PI in a different field
    if event_type == "checkout.session.completed" and not pi_id:
        pi_id = data_obj.get('payment_intent')

    # Also collect our own identifiers from metadata as a robust fallback
    meta = data_obj.get('metadata') or {}
    meta_payment_id = meta.get('payment_id')  # string id of our Payment PK
    ref = meta.get('reference_number')

    # 3) Match our Payment record (transactional + row lock)
    with transaction.atomic():
        payment = None

        if pi_id:
            try:
                payment = Payment.objects.select_for_update().get(stripe_payment_intent_id=pi_id)
            except Payment.DoesNotExist:
                payment = None

        if payment is None and meta_payment_id:
            try:
                payment = Payment.objects.select_for_update().get(id=meta_payment_id)
            except Payment.DoesNotExist:
                payment = None

        if payment is None:
            logger.warning(
                "Stripe WH: No payment matched (pi=%s, meta_payment_id=%s, type=%s, ref=%s)",
                pi_id, meta_payment_id, event_type, ref
            )
            # Ack to stop infinite retries; you'll reconcile from logs later
            return JsonResponse({'status': 'ignored_no_payment'}, status=200)

        # 4) State transitions (idempotent)
        # Success-like events
        if event_type in ("payment_intent.succeeded", "charge.succeeded", "checkout.session.completed"):
            if payment.payment_status != 'confirmed':
                payment.payment_status = 'confirmed'
                # Invalidate tokens upon finalization
                payment.confirm_token = None
                payment.confirm_token_created_at = None
                payment.cancel_token = None
                payment.cancel_token_created_at = None
                payment.save(update_fields=[
                    'payment_status',
                    'confirm_token', 'confirm_token_created_at',
                    'cancel_token', 'cancel_token_created_at',
                ])
                # Ensure invoice exists (idempotent)
                try:
                    PaymentInvoice.objects.get_or_create(
                        payment=payment,
                        defaults={'issued_date': timezone.now(), 'is_paid': True}
                    )
                except Exception:
                    logger.exception("Stripe WH: failed to create invoice")

                # Fire-and-forget email (don't block webhook)
                try:
                    ok = send_payment_confirmation_email(payment)
                    if not ok:
                        logger.warning("Stripe WH: confirmation email returned False (%s)", payment.reference_number)
                except Exception:
                    logger.exception("Stripe WH: confirmation email crashed")

        # Failure-like events
        elif event_type in ("payment_intent.payment_failed", "payment_intent.canceled"):
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
