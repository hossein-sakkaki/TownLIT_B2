from django.urls import path
from apps.conversation.consumers import DialogueConsumer

websocket_urlpatterns = [
    path('ws/conversation/', DialogueConsumer.as_asgi()),
    
]