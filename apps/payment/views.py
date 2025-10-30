from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework.viewsets import GenericViewSet

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from .models import (
                PaymentSubscription, PaymentDonation, PaymentAdvertisement, PaymentShoppingCart,
                Payment, PaymentInvoice
            )
from .serializers import (
                PaymentSubscriptionSerializer, PaymentAdvertisementSerializer, 
                PaymentDonationSerializer, PaymentShoppingCartSerializer,
                PaymentSerializer, PaymentInvoiceSerializer
            )
from common.permissions import IsFullAccessAdmin
from apps.payment.mixins.payment_mixins import PaymentMixin



# PAYMENT SUBSCRIPTION VIEWSET --------------------------------------------------------------------
class PaymentSubscriptionViewSet(viewsets.ModelViewSet):
    queryset = PaymentSubscription.objects.all()
    serializer_class = PaymentSubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsFullAccessAdmin()]
        return super().get_permissions()
    

# PAYMENT ADVERTISEMENT VIEWSET -----------------------------------------------------------
class PaymentAdvertisementViewSet(viewsets.ModelViewSet):
    queryset = PaymentAdvertisement.objects.all()
    serializer_class = PaymentAdvertisementSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsFullAccessAdmin()]
        return super().get_permissions()


# PAYMENT DONATION VIEWSET ----------------------------------------------------------------
class PaymentDonationViewSet(viewsets.ModelViewSet):
    queryset = PaymentDonation.objects.all()
    serializer_class = PaymentDonationSerializer
    permission_classes = [AllowAny]
    allow_any_permission = True
    
    def get_queryset(self):
        user = self.request.user
        base_queryset = self.queryset.exclude(payment_status='expired')

        # Staff: see all (excluding expired)
        if user.is_staff:
            return base_queryset

        # Special access for token-based confirmation/rejection
        if self.action in ("reject_payment", "confirm_payment"):
            return self.queryset

        # Authenticated user
        if user.is_authenticated:
            return base_queryset.filter(user=user)

        # Anonymous user
        return base_queryset.filter(user__isnull=True, is_anonymous_donor=True)


    def perform_create(self, serializer):
        instance = serializer.save()

        # Set a clear description for auditing
        donor = instance.user.name if instance.user else (instance.email or "Anonymous")
        instance.description = f"Donation by {donor} - Ref: {instance.reference_number}"
        instance.save(update_fields=["description"])
        
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', method='POST', block=True))
    @action(detail=False, methods=["post"], url_path='create-donation', permission_classes=[AllowAny])
    def create_donation(self, request):
        data = request.data.copy()

        # Honeypot: Block spam bots that fill all fields
        if data.get("company_name", "").strip():
            return Response(
                {"error": "Spam detected. Submission was blocked."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticated user
        if request.user.is_authenticated:
            data["user"] = request.user.pk

        # Anonymous users must explicitly allow anonymity
        elif not data.get("is_anonymous_donor", False):
            return Response(
                {"error": "Unauthenticated users must explicitly set 'is_anonymous_donor' to true."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate and create
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)

        return Response(
            {
                "message": "Your donation has been saved. You'll be redirected to the payment page shortly.",
                "donation": serializer.data
            },
            status=status.HTTP_201_CREATED,
            headers=headers
        )


    @action(detail=False, methods=['get'], url_path='my-donations', permission_classes=[IsAuthenticated])
    def my_donations(self, request):
        # Endpoint for users to get their own donations
        donations = self.get_queryset().filter(user=request.user)
        page = self.paginate_queryset(donations)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(donations, many=True)
        return Response(serializer.data)
    

# PAYMENT SHOPPING CART VIEWSET ----------------------------------------------------------------
class PaymentShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = PaymentShoppingCart.objects.all()
    serializer_class = PaymentShoppingCartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own shopping cart payments, while admins can see all
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically set the user field to the currently logged-in user
        serializer.save(user=self.request.user)
    
    def post_payment_action(self, payment_instance, status):
        from apps.orders.views import OrderViewSet
        order = payment_instance.shopping_cart.order_set.first()
        if not order:
            return

        # Call OrderViewSet & Confirm the order payment
        if status == 'confirmed':
            order_viewset = OrderViewSet()
            order_viewset.kwargs = {'pk': order.pk}
            request = self.request
            order_viewset.request = request
            order_viewset.confirm_payment(request)

        # Call OrderViewSet & Cancel the order
        elif status == 'rejected':
            order_viewset = OrderViewSet()
            order_viewset.kwargs = {'pk': order.pk}
            request = self.request
            order_viewset.request = request
            order_viewset.cancel_order(request)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def start_payment(self, request, pk=None):
        return super().start_payment(request, pk)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        return super().confirm_payment(request, pk)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def reject_payment(self, request, pk=None):
        return super().reject_payment(request, pk)



# PAYMENT PROCESS VIEWSET -----------------------------------------------------------------
class PaymentProcessViewSet(PaymentMixin, GenericViewSet):
    queryset = Payment.objects.all()
    permission_classes = [AllowAny]
    allow_any_permission = True

    @action(detail=True, methods=["get"], url_path="details")
    def get_payment_details(self, request, pk=None):
        payment = get_object_or_404(Payment, pk=pk)

        # --- Access Control ---
        if request.user.is_authenticated:
            if payment.user and payment.user != request.user:
                return Response({'detail': 'Not authorized to view this payment.'}, status=status.HTTP_403_FORBIDDEN)

        elif payment.user_id is not None:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        elif not payment.is_anonymous_donor:
            return Response({'detail': 'Unauthorized access to this payment.'}, status=status.HTTP_403_FORBIDDEN)

        # --- Choose Serializer ---
        if hasattr(payment, 'paymentdonation'):
            serializer = PaymentSerializer(payment, context={'request': request})
            
        elif hasattr(payment, 'paymentsubscription'):
            serializer = PaymentSerializer(payment)
            
        elif hasattr(payment, 'paymentadvertisement'):
            serializer = PaymentSerializer(payment)
            
        elif hasattr(payment, 'paymentshoppingcart'):
            serializer = PaymentSerializer(payment)
            
        else:
            serializer = PaymentSerializer(payment)

        return Response(serializer.data, status=status.HTTP_200_OK)


# PAYMENT INVOICE VIEWSET -----------------------------------------------------------------
class PaymentInvoiceViewSet(viewsets.ModelViewSet):
    queryset = PaymentInvoice.objects.all()
    serializer_class = PaymentInvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsFullAccessAdmin()]
        return super().get_permissions()
    
    
