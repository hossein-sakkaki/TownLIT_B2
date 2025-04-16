from django.urls import path
from .consumers import MainNotificationConsumer

websocket_urlpatterns = [
    path('ws/notifications/', MainNotificationConsumer.as_asgi()),
]
