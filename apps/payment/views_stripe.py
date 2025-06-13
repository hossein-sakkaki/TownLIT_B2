import stripe
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from apps.payment.models import Payment, PaymentInvoice
from utils.email.email_tools import send_custom_email
from .utils import send_payment_confirmation_email, send_payment_rejection_email
import logging

logger = logging.getLogger(__name__)



@csrf_exempt
def stripe_webhook_view(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)  # Invalid payload
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)  # Invalid signature

    # ---------- ✅ Success Case ----------
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_intent_id = intent['id']

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
        except Payment.DoesNotExist:
            return HttpResponse(status=404)

        if payment.payment_status != 'confirmed':
            payment.payment_status = 'confirmed'
            payment.confirm_token = None
            payment.confirm_token_created_at = None
            payment.cancel_token = None
            payment.cancel_token_created_at = None
            payment.save()

            # ✅ Create Invoice
            PaymentInvoice.objects.create(
                payment=payment,
                issued_date=timezone.now(),
                is_paid=True
            )

            # ✅ Send General Payment Confirmation Email
            success = send_payment_confirmation_email(payment)
            if not success:
                logger.warning(f"⚠️ Failed to send confirmation email for payment {payment.reference_number}")


    # ---------- ✅ Canceled Case ----------
    elif event['type'] == 'payment_intent.canceled':
        intent = event['data']['object']
        payment_intent_id = intent['id']

        try:
            payment = Payment.objects.get(stripe_payment_intent_id=payment_intent_id)
        except Payment.DoesNotExist:
            return HttpResponse(status=404)

        if payment.payment_status == 'pending':
            payment.payment_status = 'rejected'
            payment.confirm_token = None
            payment.confirm_token_created_at = None
            payment.cancel_token = None
            payment.cancel_token_created_at = None
            payment.save()

            # Unified rejection email sender
            reject = send_payment_rejection_email(payment)
            if not reject:
                logger.warning(f"⚠️ Failed to send rejection email for payment {payment.reference_number}")

    return JsonResponse({'status': 'success'})
