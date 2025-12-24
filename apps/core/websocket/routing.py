# apps/core/websocket/routing.py
from django.urls import re_path
from apps.core.websocket.consumer import CentralWebSocketConsumer

websocket_urlpatterns = [
    re_path(r"ws/?$", CentralWebSocketConsumer.as_asgi()),
]