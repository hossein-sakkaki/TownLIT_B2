from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory, DeliveryInformation, ReturnRequest, ShoppingCart, ShoppingCartItem
from apps.profiles.serializers import CustomerSerializer
from apps.products.serializers import ProductSerializer
from apps.warehouse.serializers import TemporaryReservationSerializer

# ORDER SERIALIZER ---------------------------------------------------------------------------
class OrderSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    billing_address = serializers.StringRelatedField()
    shipping_address = serializers.StringRelatedField()
    status_history = serializers.StringRelatedField(many=True, read_only=True)
    delivery_info = serializers.StringRelatedField(read_only=True)
    temporary_reservations = TemporaryReservationSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'store', 'order_date', 'status', 'billing_address', 'shipping_address', 'total_price',
                  'notes', 'status_history', 'delivery_info', 'is_help_requested', 'help_message']
        read_only_fields = ['id', 'order_date', 'status_history', 'delivery_info']

# ORDER ITEM SERIALIZER -----------------------------------------------------------------------
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'order', 'product', 'quantity', 'price_at_purchase']
        read_only_fields = ['id', 'order', 'price_at_purchase']

# ORDER STATUS HISTORY SERIALIZER -------------------------------------------------------------
class OrderStatusHistorySerializer(serializers.ModelSerializer):
    order = serializers.StringRelatedField(read_only=True)
    changed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'order', 'status', 'change_date', 'changed_by']
        read_only_fields = ['id', 'order', 'change_date', 'changed_by']

# DELIVERY INFORMATION SERIALIZER -------------------------------------------------------------
class DeliveryInformationSerializer(serializers.ModelSerializer):
    order = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = DeliveryInformation
        fields = ['id', 'order', 'carrier', 'tracking_number', 'estimated_delivery_date', 'actual_delivery_date', 'carrier_contact_number', 'status', 'tracking_url']
        read_only_fields = ['id', 'order']

# RETURN REQUEST SERIALIZER -------------------------------------------------------------------
class ReturnRequestSerializer(serializers.ModelSerializer):
    order_item = OrderItemSerializer(read_only=True)
    handled_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ReturnRequest
        fields = ['id', 'order_item', 'request_date', 'reason', 'status', 'handled_by']
        read_only_fields = ['id', 'order_item', 'request_date', 'handled_by']

# SHOPPING CART SERIALIZER --------------------------------------------------------------------
class ShoppingCartSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    items = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = ShoppingCart
        fields = ['id', 'customer', 'created_at', 'updated_at', 'items']
        read_only_fields = ['id', 'created_at', 'updated_at', 'items']

# SHOPPING CART ITEM SERIALIZER ---------------------------------------------------------------
class ShoppingCartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    cart = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = ShoppingCartItem
        fields = ['id', 'cart', 'product', 'quantity']
        read_only_fields = ['id', 'cart']

