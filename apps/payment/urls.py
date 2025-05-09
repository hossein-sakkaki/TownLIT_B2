from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PaymentDonationViewSet, PaymentShoppingCartViewSet
from .views_stripe import stripe_webhook_view


# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'donations', PaymentDonationViewSet, basename='paymentdonation')
router.register(r'shopping-cart-payments', PaymentShoppingCartViewSet, basename='paymentshoppingcart')


app_name = 'payment'
urlpatterns = [
    path('', include(router.urls)),
    path('stripe/webhook/', stripe_webhook_view, name='stripe-webhook'),
]