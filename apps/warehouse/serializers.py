from rest_framework import serializers
from .models import Warehouse, WarehouseInventory, StockMovement, TemporaryReservation


# Warehouse Serializer ----------------------------------------------------------
class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location', 'warehouse_address', 'store', 'created_at', 'updated_at', 'is_temporarily_closed', 'is_active']
        read_only_fields = ['id', 'created_at', 'updated_at', 'is_active']


# Warehouse Inventory Serializer ------------------------------------------------
class WarehouseInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WarehouseInventory
        fields = ['id', 'warehouse', 'product', 'quantity', 'reserved_quantity', 'last_updated', 'is_active']
        read_only_fields = ['id', 'last_updated', 'is_active']


# Stock Movement Serializer -----------------------------------------------------
class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = ['id', 'warehouse', 'product', 'quantity', 'movement_type', 'description', 'date']
        read_only_fields = ['id', 'date']



# TEMPORARY RESERVATION Serializer --------------------------------------------------------------

class TemporaryReservationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TemporaryReservation
        fields = ['product', 'quantity', 'expiry_date']
        read_only_fields = ['product', 'quantity', 'expiry_date']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        return value
