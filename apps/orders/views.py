from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import Order, OrderItem, OrderStatusHistory, DeliveryInformation, ReturnRequest, ShoppingCart, ShoppingCartItem
from .serializers import (
                    OrderSerializer, OrderItemSerializer, OrderStatusHistorySerializer, 
                    DeliveryInformationSerializer, ReturnRequestSerializer, ShoppingCartSerializer, ShoppingCartItemSerializer
                )
from common.permissions import IsFullAccessAdmin, IsLimitedAccessAdmin
from apps.payment.views import PaymentShoppingCartViewSet
from apps.payment.models import PaymentShoppingCart
from apps.orders.constants import DELIVERY_IN_PAYMENT, DELIVERY_PAID, DELIVERY_CANCELLED, DELIVERY_AWAITING_HELP
from apps.warehouse.models import TemporaryReservation
from apps.warehouse.utils import create_temporary_reservation
from apps.warehouse.signals.signals import clean_expired_reservations

# ORDER VIEWSET --------------------------------------------------------------------------------
class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy', 'process_payment', 'confirm_payment', 'cancel_order']:
            return [IsFullAccessAdmin()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def process_payment(self, request, pk=None):
        clean_expired_reservations()
        order = self.get_object()
        payment_cart = PaymentShoppingCart.objects.create(
            user=request.user,
            amount=order.total_price,
            shopping_cart=order.shopping_cart,
        )
        payment_viewset = PaymentShoppingCartViewSet()
        payment_viewset.request = request  # Pass the current request to the payment viewset
        response = payment_viewset.start_payment(request, pk=payment_cart.pk)
        order.status = DELIVERY_IN_PAYMENT
        order.save()
        return response

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_payment(self, request, pk=None):
        clean_expired_reservations()
        order = self.get_object()
        # Logic for confirming payment
        order.status = DELIVERY_PAID
        order.save()
        TemporaryReservation.objects.filter(order_item__order=order).delete()
        return Response({'status': 'Payment confirmed'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel_order(self, request, pk=None):
        clean_expired_reservations()
        order = self.get_object()
        # Logic for canceling the order
        order.status = DELIVERY_CANCELLED
        order.save()
        for item in order.orderitem_set.all():
            item.product.warehouse_inventory.quantity += item.quantity
            item.product.warehouse_inventory.save()
        TemporaryReservation.objects.filter(order_item__order=order).delete()
        return Response({'status': 'Order canceled'}, status=status.HTTP_200_OK)

    # ACTION FOR REQUESTING HELP --------------------------------------------------------------------    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def request_help(self, request, pk=None):
        order = self.get_object()
        if not request.user.is_member or not request.user.member.is_verified_identity:
            return Response({'error': 'You must be a verified member to request help.'}, status=status.HTTP_403_FORBIDDEN)
        help_message = request.data.get('help_message', None)
        if not help_message:
            return Response({'error': 'Help message is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Remove temporary reservations and restore inventory
        for item in order.orderitem_set.all():
            item.product.warehouse_inventory.quantity += item.quantity
            item.product.warehouse_inventory.save()
        TemporaryReservation.objects.filter(order_item__order=order).delete()
        order.is_help_requested = True
        order.help_message = help_message
        order.status = DELIVERY_AWAITING_HELP
        order.save()
        return Response({'status': 'Help request submitted successfully.'}, status=status.HTTP_200_OK)

    # ACTION FOR UPDATING HELP REQUEST ------------------------------------------------------------
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_help_request(self, request, pk=None):
        order = self.get_object()
        if not order.is_help_requested:
            return Response({'error': 'No help request exists for this order.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.user != request.user:
            return Response({'error': 'You do not have permission to update this help request.'}, status=status.HTTP_403_FORBIDDEN)
        help_message = request.data.get('help_message', None)
        if not help_message:
            return Response({'error': 'Help message is required.'}, status=status.HTTP_400_BAD_REQUEST)
        order.help_message = help_message
        order.save()
        return Response({'status': 'Help request updated successfully.'}, status=status.HTTP_200_OK)

    # ACTION FOR DELETING HELP REQUEST AND ORDER -------------------------------------------------
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def delete_help_request(self, request, pk=None):
        order = self.get_object()
        if not order.is_help_requested:
            return Response({'error': 'No help request exists for this order.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.user != request.user:
            return Response({'error': 'You do not have permission to delete this order.'}, status=status.HTTP_403_FORBIDDEN)
        order.delete()
        return Response({'status': 'Order deleted successfully.'}, status=status.HTTP_200_OK)

    # ACTION FOR PROCEEDING WITH PAYMENT AFTER CANCELING HELP REQUEST ----------------------------
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def proceed_with_payment(self, request, pk=None):
        order = self.get_object()
        if not order.is_help_requested:
            return Response({'error': 'No help request exists for this order.'}, status=status.HTTP_400_BAD_REQUEST)
        if order.user != request.user:
            return Response({'error': 'You do not have permission to proceed with payment for this order.'}, status=status.HTTP_403_FORBIDDEN)
        payment_cart = PaymentShoppingCart.objects.create(
            user=request.user,
            amount=order.total_price,
            shopping_cart=order.shopping_cart,
        )
        payment_viewset = PaymentShoppingCartViewSet()
        payment_viewset.request = request
        response = payment_viewset.start_payment(request, pk=payment_cart.pk)
        order.is_help_requested = False
        order.help_message = None
        order.status = DELIVERY_IN_PAYMENT
        order.save()
        return response
    
    # ACTION FOR REVIEWING HELP REQUESTS -----------------------------------------------------------
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def list_help_requests(self, request):
        orders = Order.objects.filter(is_help_requested=True)
        page = self.paginate_queryset(orders)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    # ACTION FOR HELP REQUESTS PAYMENT ------------------------------------------------------------
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def help_payment(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk)
        if not order.is_help_requested:
            return Response({'error': 'No help request exists for this order.'}, status=status.HTTP_400_BAD_REQUEST)
        payment_cart = PaymentShoppingCart.objects.create(
            user=request.user,
            amount=order.total_price,
            shopping_cart=order.shopping_cart,
        )
        payment_viewset = PaymentShoppingCartViewSet()
        payment_viewset.request = request
        response = payment_viewset.start_payment(request, pk=payment_cart.pk)
        
        order.status = DELIVERY_IN_PAYMENT
        order.save()
        return response
    
    


# SHOPPING CART VIEWSET -----------------------------------------------------------------------
class ShoppingCartViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCart.objects.all()
    serializer_class = ShoppingCartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShoppingCart.objects.filter(customer=self.request.user.customer)
    
    def list(self, request, *args, **kwargs):
        clean_expired_reservations()
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        clean_expired_reservations()
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def clear_cart(self, request, pk=None):
        cart = self.get_object()
        for item in cart.items.all():
            item.product.warehouse_inventory.quantity += item.quantity
            item.product.warehouse_inventory.save()
        TemporaryReservation.objects.filter(order_item__cart=cart).delete()
        cart.items.all().delete()
        return Response({'status': 'Cart cleared and all reservations deleted'}, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def create_order(self, request, pk=None):
        clean_expired_reservations()
        cart = self.get_object()
        if not cart.items.exists():
            return Response({'error': 'Shopping cart is empty.'}, status=status.HTTP_400_BAD_REQUEST)
        order = Order.objects.create(
            user=request.user,
            shopping_cart=cart,
            total_price=sum(item.product.price * item.quantity for item in cart.items.all())
        )
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
        cart.items.all().delete()
        return Response({'status': 'Order created successfully', 'order_id': order.pk}, status=status.HTTP_201_CREATED)


# SHOPPING CART ITEM VIEWSET ------------------------------------------------------------------
class ShoppingCartItemViewSet(viewsets.ModelViewSet):
    queryset = ShoppingCartItem.objects.all()
    serializer_class = ShoppingCartItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ShoppingCartItem.objects.filter(cart__customer=self.request.user.customer)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def update_quantity(self, request, pk=None):
        clean_expired_reservations()
        cart_item = self.get_object()
        operation = request.data.get('operation')  # Could be 'set', 'increase', or 'decrease'
        quantity = request.data.get('quantity')

        if operation not in ['set', 'increase', 'decrease']:
            return Response({'error': 'Invalid operation.'}, status=status.HTTP_400_BAD_REQUEST)

        if operation == 'set':
            if quantity and int(quantity) > 0:
                difference = int(quantity) - cart_item.quantity
                if difference > 0 and cart_item.product.warehouse_inventory.quantity < difference:
                    return Response({'error': 'Not enough inventory available.'}, status=status.HTTP_400_BAD_REQUEST)
                cart_item.product.warehouse_inventory.quantity -= difference
                cart_item.quantity = int(quantity)
            else:
                return Response({'error': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
            
        elif operation == 'increase':
            if quantity and int(quantity) > 0:
                if cart_item.product.warehouse_inventory.quantity < int(quantity):
                    return Response({'error': 'Not enough inventory available.'}, status=status.HTTP_400_BAD_REQUEST)
                cart_item.product.warehouse_inventory.quantity -= int(quantity)
                cart_item.quantity += int(quantity)
            else:
                return Response({'error': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)

        elif operation == 'decrease':
            if quantity and int(quantity) > 0:
                if cart_item.quantity - int(quantity) <= 0:
                    return Response({'error': 'Quantity cannot be less than 1.'}, status=status.HTTP_400_BAD_REQUEST)
                cart_item.quantity -= int(quantity)
                cart_item.product.warehouse_inventory.quantity += int(quantity)
            else:
                return Response({'error': 'Invalid quantity.'}, status=status.HTTP_400_BAD_REQUEST)
        cart_item.save()
        create_temporary_reservation(order_item=cart_item, reserved_quantity=cart_item.quantity)
        return Response({'status': 'Quantity updated and reservation created/updated'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_to_cart(self, request, pk=None):
        clean_expired_reservations()
        # Logic for adding an item to the shopping cart
        cart_item = self.get_object()
        quantity = request.data.get('quantity', 1)
        if quantity and int(quantity) > 0:
            # Check if requested quantity is available in the warehouse
            if cart_item.product.warehouse_inventory.quantity < int(quantity):
                return Response({'error': 'Not enough inventory available.'}, status=status.HTTP_400_BAD_REQUEST)
            cart_item.product.warehouse_inventory.quantity -= int(quantity)
            cart_item.product.warehouse_inventory.save()
            cart_item.quantity += int(quantity)
            cart_item.save()
            create_temporary_reservation(order_item=cart_item, reserved_quantity=cart_item.quantity)
            return Response({'status': 'Item added to cart and reservation created'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def remove_from_cart(self, request, pk=None):
        clean_expired_reservations()
        cart_item = self.get_object()
        TemporaryReservation.objects.filter(order_item=cart_item).delete()
        cart_item.product.warehouse_inventory.quantity += cart_item.quantity
        cart_item.product.warehouse_inventory.save()
        cart_item.delete()        
        return Response({'status': 'Item removed from cart and reservation deleted'}, status=status.HTTP_200_OK)












# DELIVERY INFORMATION VIEWSET ----------------------------------------------------------------
class DeliveryInformationViewSet(viewsets.ModelViewSet):
    queryset = DeliveryInformation.objects.all()
    serializer_class = DeliveryInformationSerializer
    permission_classes = [IsAuthenticated, IsFullAccessAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin])
    def update_tracking_info(self, request, pk=None):
        delivery_info = self.get_object()
        tracking_number = request.data.get('tracking_number')
        tracking_link = request.data.get('tracking_link')
        if tracking_number and tracking_link:
            delivery_info.tracking_number = tracking_number
            delivery_info.tracking_link = tracking_link
            delivery_info.save()
            return Response({'status': 'Tracking information updated'}, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid tracking information'}, status=status.HTTP_400_BAD_REQUEST)


# RETURN REQUEST VIEWSET ----------------------------------------------------------------------
class ReturnRequestViewSet(viewsets.ModelViewSet):
    queryset = ReturnRequest.objects.all()
    serializer_class = ReturnRequestSerializer
    permission_classes = [IsAuthenticated, IsLimitedAccessAdmin]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsLimitedAccessAdmin])
    def approve_return(self, request, pk=None):
        return_request = self.get_object()
        return_request.status = 'approved'
        return_request.save()
        return Response({'status': 'Return request approved'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsLimitedAccessAdmin])
    def reject_return(self, request, pk=None):
        return_request = self.get_object()
        return_request.status = 'rejected'
        return_request.save()
        return Response({'status': 'Return request rejected'}, status=status.HTTP_200_OK)
    

# ORDER ITEM VIEWSET --------------------------------------------------------------------------
class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]


# ORDER STATUS HISTORY VIEWSET ----------------------------------------------------------------
class OrderStatusHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrderStatusHistory.objects.all()
    serializer_class = OrderStatusHistorySerializer
    permission_classes = [IsAuthenticated]