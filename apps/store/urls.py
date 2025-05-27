from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import StoreViewSet
from apps.products.views import CompareProductView

router = DefaultRouter()
router.register(r'stores', StoreViewSet, basename='store')

urlpatterns = router.urls + [
    path('compare-products/', CompareProductView.as_view(), name='compare-products'),
]
