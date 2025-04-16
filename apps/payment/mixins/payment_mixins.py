import paypalrestsdk
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.payment.models import PaymentInvoice
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model, login

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

    
    @action(detail=True, methods=['post'], permission_classes=None)
    def start_payment(self, request, pk=None):
        self.configure_paypal()
        payment_instance = self.get_object()

        # Step 1: Check if user is authenticated
        if isinstance(request.user, AnonymousUser):
            email = request.data.get('email')
            password = request.data.get('password')
            if not email or not password:
                return Response({'error': 'Email and password are required for payment.'}, status=status.HTTP_400_BAD_REQUEST)
            user = CustomUser.objects.create_user(email=email, password=password)
            login(request, user)
            payment_instance.user = user
            payment_instance.save()
        self.configure_paypal()
        payment_instance = self.get_object()

        # Step 1: Create PayPal payment
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {
                "payment_method": "paypal"
            },
            "redirect_urls": {
                "return_url": request.build_absolute_uri(reverse('payment:confirm_payment', args=[payment_instance.pk])),
                "cancel_url": request.build_absolute_uri(reverse('payment:cancel_payment', args=[payment_instance.pk])),
            },
            "transactions": [{
                "amount": {
                    "total": str(payment_instance.amount),
                    "currency": "USD"
                },
                "description": "Payment for TownLIT mission."
            }]
        })
        if payment.create():
            # Get approval URL to redirect user to PayPal
            for link in payment.links:
                if link.rel == "approval_url":
                    return Response({'approval_url': link.href}, status=status.HTTP_200_OK)
        else:
            return Response({'error': payment.error}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        self.configure_paypal()
        payment_instance = self.get_object()
        if payment_instance.payment_status == 'confirmed':
            return Response({'error': 'This payment has already been confirmed.'}, status=status.HTTP_400_BAD_REQUEST)
        if payment_instance.user != request.user:
            return Response({'error': 'You do not have permission to confirm this payment.'}, status=status.HTTP_403_FORBIDDEN)
        self.configure_paypal()
        payment_instance = self.get_object()

        # Check if the logged-in user matches the payment user
        if payment_instance.user != request.user:
            return Response({'error': 'You do not have permission to confirm this payment.'}, status=status.HTTP_403_FORBIDDEN)
        self.configure_paypal()
        payment_instance = self.get_object()
        payment_id = request.query_params.get('paymentId')
        payer_id = request.query_params.get('PayerID')

        # Step 2: Execute PayPal payment
        payment = paypalrestsdk.Payment.find(payment_id)

        if payment.execute({"payer_id": payer_id}):
            payment_instance.payment_status = 'confirmed'
            payment_instance.save()

            # Step 3: Generate Invoice
            PaymentInvoice.objects.create(
                payment=payment_instance,
                issued_date=timezone.now(),
                is_paid=True,
                due_date=None
            )
            self.post_payment_action(payment_instance, status='confirmed')
            return Response({'status': 'Payment confirmed successfully'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': payment.error}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject_payment(self, request, pk=None):
        payment_instance = self.get_object()

        # Check if the payment is already confirmed
        if payment_instance.payment_status == 'confirmed':
            return Response({'error': 'Cannot reject a confirmed payment.'}, status=status.HTTP_400_BAD_REQUEST)
        if payment_instance.payment_status != 'confirmed':
            payment_instance.payment_status = 'rejected'
            payment_instance.save()
            self.post_payment_action(payment_instance, status='rejected')
            # Check if an invoice exists for the payment
            try:
                invoice = payment_instance.invoice
                invoice_number = invoice.invoice_number
            except PaymentInvoice.DoesNotExist:
                invoice_number = None
            return Response({'status': 'Payment rejected successfully', 'invoice_number': invoice_number}, status=status.HTTP_200_OK)
        payment_instance = self.get_object()
        if payment_instance.payment_status != 'confirmed':
            payment_instance.payment_status = 'rejected'
            payment_instance.save()
            # Check if an invoice exists for the payment
            try:
                invoice = payment_instance.invoice
                invoice_number = invoice.invoice_number
            except PaymentInvoice.DoesNotExist:
                invoice_number = None
            return Response({'status': 'Payment rejected successfully', 'invoice_number': invoice_number}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Cannot reject a confirmed payment.'}, status=status.HTTP_400_BAD_REQUEST)
