# apps/conversation/services/rate_limits.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-17.
# Last Update by Hossein Sakkaki on 2026-10-18.
#

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from django.conf import settings
from django.core.cache import caches
from rest_framework.throttling import SimpleRateThrottle


class _AuthenticatedMessengerRateThrottle(SimpleRateThrottle):
    setting_name = ""
    default_rate = ""

    def __init__(self):
        # One shared Redis backend for HTTP + WebSocket and all workers.
        self.cache = caches["messenger_throttle"]
        super().__init__()

    def get_rate(self):
        configured = getattr(settings, self.setting_name, None)
        return str(configured or self.default_rate)

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": str(user.pk),
        }


class MessengerSendRateThrottle(_AuthenticatedMessengerRateThrottle):
    scope = "messenger_send"
    setting_name = "MESSENGER_SEND_THROTTLE_RATE"
    default_rate = "30/min"


class MessengerMediaRateThrottle(_AuthenticatedMessengerRateThrottle):
    scope = "messenger_media"
    setting_name = "MESSENGER_MEDIA_THROTTLE_RATE"
    default_rate = "10/min"


class MessengerWorkflowRateThrottle(_AuthenticatedMessengerRateThrottle):
    scope = "messenger_workflow"
    setting_name = "MESSENGER_WORKFLOW_THROTTLE_RATE"
    default_rate = "60/min"


@dataclass(frozen=True)
class MessengerRateLimitResult:
    allowed: bool
    retry_after_seconds: int | None = None


def check_messenger_rate_limit(*, user, throttle_class) -> MessengerRateLimitResult:
    """Run the same DRF throttle implementation for realtime mutations."""
    throttle = throttle_class()
    request = SimpleNamespace(
        user=user,
        META={},
    )

    if throttle.allow_request(request, None):
        return MessengerRateLimitResult(allowed=True)

    wait = throttle.wait()
    retry_after = max(1, int(wait or 1))
    return MessengerRateLimitResult(
        allowed=False,
        retry_after_seconds=retry_after,
    )
