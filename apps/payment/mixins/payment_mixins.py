import paypalrestsdk
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseRedirect
from uuid import uuid4

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404

from apps.payment.models import PaymentInvoice, PaymentDonation, PaymentSubscription, PaymentAdvertisement, PaymentShoppingCart, Payment
from django.contrib.auth import get_user_model, login
from apps.payment.stripe_utils import create_stripe_payment_intent

CustomUser = get_user_model()



# PAYMENT Mixin ---------------------------------------------------------------------------------------
class PaymentMixin:
    @classmethod
    def configure_paypal(cls):
        paypalrestsdk.configure({
            "mode": settings.PAYPAL_MODE,
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_SECRET_KEY,
        })
    
    def get_permissions(self):
        if getattr(self, 'allow_any_permission', False):
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def post_payment_action(self, payment_instance, status): # Just for PaymentShoppingCartViewSet
        """
            status (str): Either 'confirmed' or 'rejected'.
        """
        pass

    def get_payment_type_param(self, payment_instance) -> str:
        if isinstance(payment_instance, PaymentDonation):
            return "donation"
        elif isinstance(payment_instance, PaymentSubscription):
            return "subscription"
        elif isinstance(payment_instance, PaymentAdvertisement):
            return "ads"
        elif isinstance(payment_instance, PaymentShoppingCart):
            return "shop"
        return "unknown"


    # -------------------- START ----------------------
    @action(detail=True, methods=['post'], url_path='start-payment', permission_classes=[AllowAny])
    def start_payment(self, request, pk=None):
        self.configure_paypal()
        payment_instance = self.get_object()

        # Attach user if not already set
        if payment_instance.user_id is None:
            if payment_instance.is_anonymous_donor:
                pass
            elif request.user.is_authenticated:
                payment_instance.user = request.user
            else:
                return Response(
                    {'error': 'User must be authenticated or donation must be marked as anonymous.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Generate a secure cancel token
        cancel_token = uuid4().hex
        payment_instance.cancel_token = cancel_token
        payment_instance.cancel_token_created_at = timezone.now()
        
        confirm_token = uuid4().hex
        payment_instance.confirm_token = confirm_token
        payment_instance.confirm_token_created_at = timezone.now()

        payment_instance.save()

        # Create PayPal payment
        paypal_payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": request.build_absolute_uri(
                    f"/payment/donations/{payment_instance.pk}/confirm-payment/?confirm_token={confirm_token}"
                ),
                "cancel_url": request.build_absolute_uri(
                    f"/payment/donations/{payment_instance.pk}/reject-payment/?cancel_token={cancel_token}"
                ),

            },
            "transactions": [{
                "amount": {
                    "total": str(payment_instance.amount),
                    "currency": "CAD"
                },
                "description": "Payment for TownLIT mission."
            }]
        })

        if paypal_payment.create():
            for link in paypal_payment.links:
                if link.rel == "approval_url":
                    return Response({'approval_url': link.href}, status=status.HTTP_200_OK)
        else:
            return Response({'error': paypal_payment.error}, status=status.HTTP_400_BAD_REQUEST)


    # -------------------- PAYMENT ----------------------
    @action(detail=True, methods=['get'], url_path='confirm-payment', permission_classes=[AllowAny])
    def confirm_payment(self, request, pk=None):
        self.configure_paypal()
        payment_instance = self.get_object()

        # If already confirmed, no need to process again
        if payment_instance.payment_status == 'confirmed':
            type_param = self.get_payment_type_param(payment_instance)
            return HttpResponseRedirect(
                f"{settings.FRONTEND_BASE_URL}/payment/result?status=success&type={type_param}&ref={payment_instance.reference_number}"
            )    

        # ✅ Validate confirm token (not user session)
        confirm_token = request.query_params.get("confirm_token")
        if not confirm_token or not payment_instance.is_valid_confirm_token(confirm_token):
            return Response(
                {'error': 'Invalid or expired confirm token.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate PayPal parameters
        payment_id = request.query_params.get('paymentId')
        payer_id = request.query_params.get('PayerID')

        if not payment_id or not payer_id:
            return Response(
                {'error': 'Missing PayPal confirmation parameters.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Execute confirmation with PayPal
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            if payment.execute({"payer_id": payer_id}):
                payment_instance.payment_status = 'confirmed'
                payment_instance.confirm_token = None  # 🔐 invalidate after use
                payment_instance.confirm_token_created_at = None
                payment_instance.save()

                PaymentInvoice.objects.create(
                    payment=payment_instance,
                    issued_date=timezone.now(),
                    is_paid=True
                )

                self.post_payment_action(payment_instance, status='confirmed')

                type_param = self.get_payment_type_param(payment_instance)
                return HttpResponseRedirect(
                    f"{settings.FRONTEND_BASE_URL}/payment/result?status=success&type={type_param}&ref={payment_instance.reference_number}"
                )
            
            else:
                return Response({'error': payment.error}, status=status.HTTP_400_BAD_REQUEST)
        except paypalrestsdk.ResourceNotFound as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)


    # -------------------- REJECT ----------------------
    @action(detail=True, methods=['get', 'post'], url_path='reject-payment', permission_classes=[AllowAny])
    def reject_payment(self, request, pk=None):
        payment_instance = self.get_object()

        # Prevent re-rejection if already confirmed
        if payment_instance.payment_status == 'confirmed':
            type_param = self.get_payment_type_param(payment_instance)
            return HttpResponseRedirect(
                f"{settings.FRONTEND_BASE_URL}/payment/result?status=success&type={type_param}&ref={payment_instance.reference_number}"
            )

        # Validate cancel token
        token = request.query_params.get("cancel_token")
        if not token or not payment_instance.is_valid_cancel_token(token):
            return Response(
                {'error': 'Invalid or expired cancel token.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Proceed with rejection
        payment_instance.payment_status = 'rejected'
        payment_instance.cancel_token = None  # ❌ Invalidate token after use
        payment_instance.cancel_token_created_at = None
        payment_instance.save()
        self.post_payment_action(payment_instance, status='rejected')

        type_param = self.get_payment_type_param(payment_instance)
        return HttpResponseRedirect(
            f"{settings.FRONTEND_BASE_URL}/payment/result?status=cancel&type={type_param}&ref={payment_instance.reference_number}"
        )

    # -------------------- RETRY ----------------------
    @action(detail=True, methods=['post'], url_path='retry-payment', permission_classes=[AllowAny])
    def retry_payment(self, request, pk=None):
        payment_instance = self.get_object()

        if payment_instance.payment_status not in ['rejected', 'failed']:
            return Response(
                {"error": "Payment is not in a retryable state."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reset status and regenerate tokens
        payment_instance.payment_status = 'pending'
        payment_instance.cancel_token = uuid4().hex
        payment_instance.cancel_token_created_at = timezone.now()
        payment_instance.confirm_token = uuid4().hex
        payment_instance.confirm_token_created_at = timezone.now()
        payment_instance.save()

        return Response({
            "id": payment_instance.id,
            "reference_number": payment_instance.reference_number,
            "type": self.get_payment_type_param(payment_instance),
            "status": payment_instance.payment_status,
        }, status=status.HTTP_200_OK)


    # -------------------- RETRY BY REF ----------------------
    @action(detail=False, methods=['post'], url_path='by-ref/(?P<ref>[\\w-]+)/retry-payment', permission_classes=[AllowAny])
    def retry_by_reference(self, request, ref=None):
        payment = get_object_or_404(Payment, reference_number=ref)

        # فقط اگر وضعیت فعلی قابل بازگشت است
        if payment.payment_status not in ['rejected', 'failed', 'expired']:
            return Response(
                {"error": "This payment is not eligible for retry."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # بازگردانی وضعیت و بازسازی توکن‌ها
        payment.payment_status = 'pending'
        payment.cancel_token = uuid4().hex
        payment.cancel_token_created_at = timezone.now()
        payment.confirm_token = uuid4().hex
        payment.confirm_token_created_at = timezone.now()
        payment.save()

        return Response({
            "id": payment.id,
            "reference_number": payment.reference_number,
            "type": self.get_payment_type_param(payment),
            "status": payment.payment_status,
        }, status=status.HTTP_200_OK)
        

    # -------------------- START STRIPE PAYMENT ----------------------
    @action(detail=True, methods=['post'], url_path='start-stripe-payment', permission_classes=[AllowAny])
    def start_stripe_payment(self, request, pk=None):
        payment_instance = self.get_object()

        # 1. تعیین کاربر
        if payment_instance.user_id is None:
            if payment_instance.is_anonymous_donor:
                pass  # قابل قبول است
            elif request.user.is_authenticated:
                payment_instance.user = request.user
            else:
                return Response(
                    {'error': 'User must be authenticated or donation must be marked as anonymous.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if not payment_instance.cancel_token:
            payment_instance.cancel_token = uuid4().hex
            payment_instance.cancel_token_created_at = timezone.now()

        if not payment_instance.confirm_token:
            payment_instance.confirm_token = uuid4().hex
            payment_instance.confirm_token_created_at = timezone.now()

        payment_instance.save()

        # 3. ساخت PaymentIntent از طریق Stripe
        try:
            client_secret = create_stripe_payment_intent(payment_instance)
            type_param = self.get_payment_type_param(payment_instance)
            return Response({
                "client_secret": client_secret,
                "payment_id": payment_instance.id,
                "reference_number": payment_instance.reference_number,
                "type": type_param,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

    # ----------------------- CANCEL PAYMENT ------------------------
    @action(detail=True, methods=["post"], url_path="cancel-payment", permission_classes=[AllowAny])
    def cancel_payment(self, request, pk=None):
        payment_instance = self.get_object()

        # Only allow canceling pending or expired (not finalized)
        if payment_instance.payment_status in ["confirmed", "rejected", "canceled"]:
            return Response(
                {"error": "This payment is already finalized and cannot be canceled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment_instance.payment_status = "canceled"
        payment_instance.save(update_fields=["payment_status"])

        # Optional: Post-cancel hook if needed in subclasses
        self.post_payment_action(payment_instance, status="canceled")

        return Response({"message": "Payment canceled successfully."}, status=status.HTTP_200_OK)
