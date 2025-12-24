# apps/core/websocket/router.py
# ===================================================================
#     WebSocket Handler Router — App-level Dynamic Dispatcher
# ===================================================================

import logging

logger = logging.getLogger(__name__)

class WebSocketRouter:
    """
    Central registry for WebSocket handlers.
    Example:
        register("conversation", ConversationHandler)
        register("comments", CommentsHandler)
        register("notifications", NotificationWSHandler)
    """

    def __init__(self):
        self._registry = {}

    def register(self, app_name: str, handler_cls):
        """Register a handler class for a given app name."""
        self._registry[app_name] = handler_cls

    def get_handler(self, app_name: str, consumer):
        """Return a new handler instance for the given app name."""
        handler_cls = self._registry.get(app_name)
        if not handler_cls:
            return None
        return handler_cls(consumer)


# Create global router instance
ws_router = WebSocketRouter()
