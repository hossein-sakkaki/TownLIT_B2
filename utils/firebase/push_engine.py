# utils/firebase/push_engine.py

from typing import List, Optional, Dict, Any
import logging
import requests

from django.conf import settings
from apps.accounts.models.devices import UserDeviceKey
from .google_oauth import get_google_access_token


logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Helper → stringify data
# ------------------------------------------------------------
def _stringify_dict(
    data: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    if not data:
        return {}

    safe = {}

    for key, value in data.items():
        safe[str(key)] = (
            ""
            if value is None
            else str(value)
        )

    return safe


# ------------------------------------------------------------
# Firebase Engine
# ------------------------------------------------------------
class FirebasePushEngine:
    """
    FCM HTTP v1 push engine.

    Important:
    - Android/Web push tokens go through FCM.
    - Native iOS APNs tokens must NOT be sent to FCM.
    """

    def __init__(self):
        self.project_id = getattr(
            settings,
            "FIREBASE_PROJECT_ID",
            None,
        )

        if not self.project_id:
            logger.error(
                "⛔ FIREBASE_PROJECT_ID missing"
            )

        self.base_url = (
            "https://fcm.googleapis.com/v1/"
            f"projects/{self.project_id}/"
            "messages:send"
        )

    # ------------------------------------------------------------
    # Resolve FCM-owned tokens only
    # ------------------------------------------------------------
    def get_tokens_for_user(
        self,
        user,
    ) -> List[str]:
        qs = (
            UserDeviceKey.objects
            .filter(
                user=user,
                is_active=True,
                platform__in=[
                    "android",
                    "web",
                ],
            )
            .exclude(
                push_token__isnull=True
            )
            .exclude(
                push_token__exact=""
            )
        )

        return list(
            qs.values_list(
                "push_token",
                flat=True,
            )
        )

    # ------------------------------------------------------------
    # Send to one FCM token
    # ------------------------------------------------------------
    def _send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[
            Dict[str, Any]
        ] = None,
    ) -> bool:
        if not self.project_id:
            logger.error(
                "⛔ Cannot send FCM push: "
                "FIREBASE_PROJECT_ID missing"
            )
            return False

        token = (
            token
            or ""
        ).strip()

        if not token:
            return False

        try:
            access_token = (
                get_google_access_token()
            )

            headers = {
                "Authorization":
                    f"Bearer {access_token}",

                "Content-Type":
                    "application/json; charset=utf-8",
            }

            base_data: Dict[str, Any] = (
                data.copy()
                if data
                else {}
            )

            base_data.setdefault(
                "title",
                title,
            )

            base_data.setdefault(
                "body",
                body,
            )

            safe_data = _stringify_dict(
                base_data
            )

            payload = {
                "message": {
                    "token": token,
                    "data": safe_data,
                }
            }

            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=10,
            )

            if (
                200
                <= response.status_code
                < 300
            ):
                logger.info(
                    "[FCM] Push sent OK "
                    "token_prefix=%s",
                    token[:12],
                )

                return True

            logger.warning(
                "[FCM] Push failed "
                "status=%s "
                "token_prefix=%s "
                "response=%s",
                response.status_code,
                token[:12],
                response.text[:1000],
            )

            return False

        except Exception as error:
            logger.exception(
                "[FCM] Exception while sending "
                "token_prefix=%s error=%s",
                token[:12],
                error,
            )

            return False

    # ------------------------------------------------------------
    # Send to multiple FCM tokens
    # ------------------------------------------------------------
    def send_to_tokens(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[
            Dict[str, Any]
        ] = None,
    ) -> int:
        if not tokens:
            return 0

        sent_count = 0

        for token in tokens:
            if self._send_to_token(
                token,
                title,
                body,
                data,
            ):
                sent_count += 1

        return sent_count

    # ------------------------------------------------------------
    # Send to one user's FCM devices
    # ------------------------------------------------------------
    def send_to_user(
        self,
        user,
        title: str,
        body: str,
        data: Optional[
            Dict[str, Any]
        ] = None,
    ) -> int:
        tokens = self.get_tokens_for_user(
            user
        )

        if not tokens:
            return 0

        return self.send_to_tokens(
            tokens,
            title,
            body,
            data or {},
        )


# Singleton
push_engine = FirebasePushEngine()