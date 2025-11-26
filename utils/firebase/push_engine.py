# utils/firebase/push_engine.py

from typing import List, Optional, Dict, Any
import logging
import requests

from django.conf import settings
from apps.accounts.models import UserDeviceKey
from .google_oauth import get_google_access_token

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Helper → stringify data (FCM requires string values)
# ------------------------------------------------------------
def _stringify_dict(data: Optional[Dict[str, Any]]) -> Dict[str, str]:
    if not data:
        return {}

    safe = {}
    for k, v in data.items():
        if v is None:
            safe[k] = ""
        else:
            safe[k] = str(v)
    return safe


# ------------------------------------------------------------
# Firebase Engine
# ------------------------------------------------------------
class FirebasePushEngine:
    """Unified engine for FCM HTTP v1 REST API."""

    def __init__(self):
        self.project_id = getattr(settings, "FIREBASE_PROJECT_ID", None)

        if not self.project_id:
            logger.error("⛔ FIREBASE_PROJECT_ID missing")

        self.base_url = (
            f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        )

    # ------------------------------------------------------------
    def get_tokens_for_user(self, user) -> List[str]:
        qs = (
            UserDeviceKey.objects
            .filter(user=user, is_active=True)
            .exclude(push_token__isnull=True)
            .exclude(push_token__exact="")
        )

        tokens = [u.push_token for u in qs]

        logger.error(
            "🔥 PUSH ENGINE: Fetching tokens for user %s → %s",
            user.id,
            tokens,
        )

        return tokens

    # ------------------------------------------------------------
    # INTERNAL: send to one device
    # ------------------------------------------------------------
    def _send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        logger.error("🔥 FCM SEND START → token=%s...", token[:15])

        if not self.project_id:
            logger.error("⛔ Cannot send → FIREBASE_PROJECT_ID missing")
            return None

        access_token = get_google_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        # STRINGIFY DATA
        safe_data = _stringify_dict(data)

        payload = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "data": safe_data,
            }
        }

        logger.error("🔥 FCM REQUEST PAYLOAD → %s", payload)

        try:
            resp = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=10,
            )

            logger.error(
                "🔥 FCM RESPONSE → status=%s body=%s",
                resp.status_code,
                resp.text,
            )

            if 200 <= resp.status_code < 300:
                return resp.json()

            logger.error("⛔ FCM FAILED → %s", resp.text)
            return None

        except Exception as e:
            logger.exception("⛔ FCM EXCEPTION → %s", e)
            return None

    # ------------------------------------------------------------
    # PUBLIC: send to multiple tokens
    # ------------------------------------------------------------
    def send_to_tokens(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        if not tokens:
            logger.info("[FCM] No tokens to send.")
            return

        for t in tokens:
            self._send_to_token(t, title, body, data)

    # ------------------------------------------------------------
    # PUBLIC: send to user
    # ------------------------------------------------------------
    def send_to_user(
        self,
        user,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        tokens = self.get_tokens_for_user(user)

        if not tokens:
            logger.info("[FCM] User %s has no active push tokens.", user.id)
            return None

        logger.info(
            "[FCM] Sending push to user %s (%s devices)",
            user.id,
            len(tokens),
        )

        return self.send_to_tokens(tokens, title, body, data or {})


# Singleton
push_engine = FirebasePushEngine()
