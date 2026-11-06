# apps/main/middleware.py

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from apps.accounts.services.session_generation_policy import (
    session_generation_enforced,
    session_generation_from_payload,
    session_generation_matches,
)
from apps.core.websocket.access_auth import _account_allows_websocket
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

        # For the legacy socket's periodic session-generation revalidation.
        # jwt.decode is repeated only with enforcement on; the signature is
        # reverified and the raw credential is never retained on the socket.
        if session_generation_enforced():
            try:
                signed = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=["HS256"]
                )
                scope["townlit_session_generation"] = (
                    session_generation_from_payload(signed)
                )
            except Exception:
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
            user = User.objects.get(id=user_id)
            if session_generation_enforced():
                if payload.get("token_type") != "access":
                    return None
                if not _account_allows_websocket(user):
                    return None
            if not session_generation_matches(
                user.pk, session_generation_from_payload(payload)
            ):
                return None
            return user
        except jwt.ExpiredSignatureError:
            logger.error("❌ JWT Error: Token has expired")
        except jwt.DecodeError:
            logger.error("❌ JWT Error: Invalid token")
        except User.DoesNotExist:
            logger.error("❌ JWT Error: User not found")
        except Exception:
            logger.warning("WebSocket authentication unavailable")

        return None


def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)
