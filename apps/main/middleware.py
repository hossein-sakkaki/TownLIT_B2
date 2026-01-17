import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
import logging

logger = logging.getLogger("django")
User = get_user_model()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            user = await self.get_user_from_token(token)
            if user:
                scope["user"] = user
            else:
                logger.warning("❌ WebSocket Authentication Failed: Invalid Token")
                await send({"type": "websocket.close"})
                return
        else:
            logger.warning("❌ WebSocket Authentication Failed: No Token Provided")
            await send({"type": "websocket.close"})
            return

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user_from_token(self, token):
        """
        Decode the JWT token and return the authenticated user.
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("user_id")
            return User.objects.get(id=user_id)
        except jwt.ExpiredSignatureError:
            logger.error("❌ JWT Error: Token has expired")
        except jwt.DecodeError:
            logger.error("❌ JWT Error: Invalid token")
        except User.DoesNotExist:
            logger.error("❌ JWT Error: User not found")

        return None


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)