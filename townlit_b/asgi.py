# townlit_b/asgi.py
import os
import django

from townlit_b.security_logging import install_sensitive_logging_filters

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "townlit_b.settings")
django.setup()
install_sensitive_logging_filters()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
# Initialize Django before importing WebSocket consumers and models.
django_asgi_app = get_asgi_application()

from apps.core.websocket.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})

