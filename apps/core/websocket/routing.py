# apps/core/websocket/routing.py
# TownLIT
#
# Last Update by Hossein Sakkaki on 2026-10-23.

from django.urls import re_path

from apps.main.middleware import JWTAuthMiddlewareStack
from apps.core.websocket.consumer import CentralWebSocketConsumer
from apps.core.websocket.consumer_v2 import CentralWebSocketConsumerV2


websocket_urlpatterns = [
    re_path(
        r"^ws/v2/?$",
        CentralWebSocketConsumerV2.as_asgi(),
    ),
    re_path(
        r"^ws/?$",
        JWTAuthMiddlewareStack(
            CentralWebSocketConsumer.as_asgi()
        ),
    ),
]
