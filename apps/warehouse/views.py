from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from .models import Warehouse, WarehouseInventory, StockMovement
from .serializers import WarehouseSerializer, WarehouseInventorySerializer, StockMovementSerializer
from common.permissions import IsFullAccessAdmin, IsLimitedAccessAdmin


# WAREHOUSE ViewSet ---------------------------------------------------------------------
class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin]

    def get_queryset(self):
        return Warehouse.objects.filter(store__organization__org_owners=self.request.user, is_active=True)

    def perform_create(self, serializer):
        store = self.request.user.organization.store_details
        serializer.save(store=store)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def toggle_active_status(self, request, pk=None):
        warehouse = self.get_object()
        warehouse.is_active = not warehouse.is_active
        warehouse.save()
        status_text = 'activated' if warehouse.is_active else 'deactivated'
        return Response({'status': f'Warehouse successfully {status_text}.'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def toggle_temporary_closure(self, request, pk=None):
        warehouse = self.get_object()
        warehouse.is_temporarily_closed = not warehouse.is_temporarily_closed
        warehouse.save()
        status_text = 'temporarily closed' if warehouse.is_temporarily_closed else 'reopened'
        return Response({'status': f'Warehouse successfully {status_text}.'}, status=status.HTTP_200_OK)


# WAREHOUSE INVENTORY ViewSet --------------------------------------------------------------------------
class WarehouseInventoryViewSet(viewsets.ModelViewSet):
    queryset = WarehouseInventory.objects.all()
    serializer_class = WarehouseInventorySerializer
    permission_classes = [IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin]

    def get_queryset(self):
        return WarehouseInventory.objects.filter(warehouse__store__organization__org_owners=self.request.user, is_active=True)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def add_stock(self, request, pk=None):
        inventory = self.get_object()
        additional_quantity = request.data.get('quantity', 0)
        if additional_quantity <= 0:
            return Response({'error': 'Quantity must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
        inventory.quantity += additional_quantity
        inventory.save()
        return Response({'status': 'Stock added successfully', 'new_quantity': inventory.quantity}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def remove_stock(self, request, pk=None):
        inventory = self.get_object()
        removal_quantity = request.data.get('quantity', 0)
        if removal_quantity <= 0:
            return Response({'error': 'Quantity must be greater than zero.'}, status=status.HTTP_400_BAD_REQUEST)
        if removal_quantity > inventory.quantity:
            return Response({'error': 'Not enough stock available.'}, status=status.HTTP_400_BAD_REQUEST)
        inventory.quantity -= removal_quantity
        inventory.save()
        return Response({'status': 'Stock removed successfully', 'new_quantity': inventory.quantity}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def update_stock(self, request, pk=None):
        inventory = self.get_object()
        new_quantity = request.data.get('quantity', None)
        if new_quantity is None or new_quantity < 0:
            return Response({'error': 'Quantity must be a non-negative number.'}, status=status.HTTP_400_BAD_REQUEST)
        inventory.quantity = new_quantity
        inventory.save()
        return Response({'status': 'Stock quantity updated successfully', 'new_quantity': inventory.quantity}, status=status.HTTP_200_OK)


# STOCK MOVEMENT ViewSet -----------------------------------------------------------------
class StockMovementViewSet(viewsets.ModelViewSet):
    queryset = StockMovement.objects.all()
    serializer_class = StockMovementSerializer
    permission_classes = [IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin]

    def get_queryset(self):
        return StockMovement.objects.filter(warehouse__store__organization__org_owners=self.request.user)

    def perform_create(self, serializer):
        serializer.save(date=timezone.now())

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsFullAccessAdmin | IsLimitedAccessAdmin])
    def move_stock(self, request, pk=None):
        stock_movement = self.get_object()
        # Logic to handle stock movement
        stock_movement.save()
        return Response({'status': 'Stock moved successfully'}, status=status.HTTP_200_OK)
