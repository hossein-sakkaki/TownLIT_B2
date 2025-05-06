from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import (
                PaymentSubscription, PaymentDonation, PaymentAdvertisement, PaymentShoppingCart,
                PaymentInvoice
            )
from .serializers import (
                PaymentSubscriptionSerializer, PaymentAdvertisementSerializer, 
                PaymentDonationSerializer, PaymentShoppingCartSerializer,
                PaymentInvoiceSerializer
            )
from apps.main.permissions import IsFullAccessAdmin
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
class PaymentDonationViewSet(viewsets.ModelViewSet, PaymentMixin):
    queryset = PaymentDonation.objects.all()
    serializer_class = PaymentDonationSerializer
    permission_classes = [AllowAny]
    allow_any_permission = True

    def get_queryset(self):
        # Users can only see their own donations, while admins can see all
        if self.request.user.is_staff:
            return self.queryset
        return self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically set the user field to the currently logged-in user
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
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
class PaymentShoppingCartViewSet(viewsets.ModelViewSet, PaymentMixin):
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







# PAYMENT INVOICE VIEWSET -----------------------------------------------------------------
class PaymentInvoiceViewSet(viewsets.ModelViewSet):
    queryset = PaymentInvoice.objects.all()
    serializer_class = PaymentInvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsFullAccessAdmin()]
        return super().get_permissions()
    
    
    