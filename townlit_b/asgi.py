# townlit_b/asgi.py
import os
import django
import asyncio

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'townlit_b.settings')
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.main.middleware import JWTAuthMiddlewareStack
from apps.core.websocket.routing import websocket_urlpatterns
from services.presence_watchdog import ensure_presence_watchdog_running


ensure_presence_watchdog_running()
# ASGI HTTP
django_asgi_app = get_asgi_application()

# Fix Python 3.10 event loop behavior
try:
    asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

# Main application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})






# import os
# import django
# import asyncio

# # ✅ Set the default Django settings module
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'townlit_b.settings')
# django.setup()

# from django.core.asgi import get_asgi_application
# from channels.routing import ProtocolTypeRouter, URLRouter
# from apps.main.middleware import JWTAuthMiddlewareStack
# import apps.posts.routing as posts_routing
# from apps.conversation import routing as conversation_routing
# from apps.notifications import routing as notifications_routing

# # ✅ Initialize the Django ASGI application for handling HTTP requests
# django_asgi_app = get_asgi_application()

# # ✅ Handling event loop manually for Python 3.10+
# try:
#     loop = asyncio.get_running_loop()
# except RuntimeError:
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)

# # ✅ Define the main application with WebSocket and HTTP support
# application = ProtocolTypeRouter({
#     "http": django_asgi_app,  # Handle HTTP requests
#     "websocket": JWTAuthMiddlewareStack(  # Secure WebSocket connections using JWT authentication
#         URLRouter(
#             conversation_routing.websocket_urlpatterns 
#             + posts_routing.websocket_urlpatterns
#             + notifications_routing.websocket_urlpatterns
#         )
#     ),
# })

