from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers
from .views import StoreViewSet
from apps.products.views import ProductViewSet, ProductGroupViewSet, CompareProductView, RiverHarvestViewSet
from apps.orders.views import OrderViewSet, DeliveryInformationViewSet, ShoppingCartViewSet, ShoppingCartItemViewSet
from apps.warehouse.views import WarehouseViewSet, WarehouseInventoryViewSet, StockMovementViewSet

# Main Router for Store
router = DefaultRouter()
router.register(r'stores', StoreViewSet, basename='store')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-groups', ProductGroupViewSet, basename='product-group')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'delivery-information', DeliveryInformationViewSet, basename='delivery-information')
router.register(r'shopping-carts', ShoppingCartViewSet, basename='shopping-cart')
router.register(r'shopping-cart-items', ShoppingCartItemViewSet, basename='shopping-cart-item')
router.register(r'river-harvest/products', RiverHarvestViewSet, basename='river-harvest-products')

# Nested Router for Products within a Store
store_router = routers.NestedSimpleRouter(router, r'stores', lookup='store')
store_router.register(r'products', ProductViewSet, basename='store-products')
store_router.register(r'warehouses', WarehouseViewSet, basename='store-warehouses')

# Nested Router for Inventory and Stock Movements within a Warehouse
warehouse_router = routers.NestedSimpleRouter(store_router, r'warehouses', lookup='warehouse')
warehouse_router.register(r'inventory', WarehouseInventoryViewSet, basename='warehouse-inventory')
warehouse_router.register(r'stock-movements', StockMovementViewSet, basename='warehouse-stock-movements')

app_name = 'store'
urlpatterns = [
    path('', include(router.urls)),
    path('', include(store_router.urls)), # /stores/{store_id}/products/
    path('', include(warehouse_router.urls)),
    path('compare-products/', CompareProductView.as_view(), name='compare-products'),
]
