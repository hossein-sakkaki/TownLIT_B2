from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import WarehouseViewSet, WarehouseInventoryViewSet, StockMovementViewSet

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'inventory', WarehouseInventoryViewSet, basename='inventory')
router.register(r'stock-movements', StockMovementViewSet, basename='stock-movement')

urlpatterns = router.urls
