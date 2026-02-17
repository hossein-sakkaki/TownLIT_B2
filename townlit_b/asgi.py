# townlit_b/asgi.py
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "townlit_b.settings")
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.main.middleware import JWTAuthMiddlewareStack
from apps.core.websocket.routing import websocket_urlpatterns

django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})

