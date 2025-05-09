import stripe
import json
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from apps.payment.models import PaymentDonation, PaymentInvoice
from utils.email.email_tools import send_custom_email

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

    # ----------------- SUCCESS CASE -----------------
    if event['type'] == 'payment_intent.succeeded':
        intent = event['data']['object']
        payment_intent_id = intent['id']

        try:
            donation = PaymentDonation.objects.get(stripe_payment_intent_id=payment_intent_id)
        except PaymentDonation.DoesNotExist:
            return HttpResponse(status=404)

        if donation.payment_status != 'confirmed':
            donation.payment_status = 'confirmed'
            donation.confirm_token = None
            donation.confirm_token_created_at = None
            donation.save()

            PaymentInvoice.objects.create(
                payment=donation,
                issued_date=timezone.now(),
                is_paid=True
            )
            
            if donation.email:
                send_custom_email(
                    to=donation.email,
                    subject="Thank You for Your Donation!",
                    template_path="emails/payment/donation_confirmed.html",
                    context={"name": donation.user.name if donation.user else "Friend", "amount": donation.amount},
                )

    # ----------------- CANCELED CASE -----------------
    elif event['type'] == 'payment_intent.canceled':
        intent = event['data']['object']
        payment_intent_id = intent['id']

        try:
            donation = PaymentDonation.objects.get(stripe_payment_intent_id=payment_intent_id)
        except PaymentDonation.DoesNotExist:
            return HttpResponse(status=404)

        if donation.payment_status == 'pending':
            donation.payment_status = 'rejected'
            donation.cancel_token = None
            donation.cancel_token_created_at = None
            donation.save()

            if donation.email:
                send_custom_email(
                    to=donation.email,
                    subject="Donation Canceled",
                    template_path="emails/payment/donation_rejected.html",
                    context={"name": donation.user.name if donation.user else "Friend"},
                )

    return JsonResponse({'status': 'success'})
