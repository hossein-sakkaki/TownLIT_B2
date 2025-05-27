from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, ProductGroupViewSet, RiverHarvestViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'product-groups', ProductGroupViewSet, basename='product-group')
router.register(r'river-harvest/products', RiverHarvestViewSet, basename='river-harvest-products')

urlpatterns = router.urls
