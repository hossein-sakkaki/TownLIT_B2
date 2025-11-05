# apps/posts/routing.py
from django.urls import re_path
from .consumers import CommentsConsumer

websocket_urlpatterns = [
    re_path(r"^ws/comments/$", CommentsConsumer.as_asgi()),  # CHANGED ✅ no URL params
]
