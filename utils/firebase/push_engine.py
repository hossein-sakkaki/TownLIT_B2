# utils/firebase/push_engine.py

import logging
from typing import Any, Dict, List, Optional

import requests
from django.db.models import Q
from django.conf import settings

from apps.accounts.models.devices import UserDeviceKey
from .google_oauth import (
    get_google_access_token,
    reset_google_access_token_cache,
)
from apps.accounts.constants.devices import (
    DEVICE_PLATFORM_ANDROID,
    DEVICE_PLATFORM_WEB,
    FCM_DEVICE_PLATFORMS,
)

logger = logging.getLogger(__name__)


ANDROID_GENERAL_CHANNEL_ID = "townlit_general"
ANDROID_MESSAGE_CHANNEL_ID = "townlit_messages"

MESSENGER_NOTIFICATION_TYPES = {
    "new_message_direct",
    "new_message_group",
    "messenger_group_created",
    "messenger_message_pinned",
    "messenger_reaction_direct",
    "messenger_reaction_group",
}

FCM_ERROR_DETAIL_TYPE = "type.googleapis.com/google.firebase.fcm.v1.FcmError"


def _stringify_dict(
    data: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Convert FCM data payload values to strings."""
    if not data:
        return {}

    return {
        str(key): "" if value is None else str(value)
        for key, value in data.items()
    }


class FirebasePushEngine:
    """
    FCM HTTP v1 push engine.

    Platform ownership:
    - Android uses FCM notification + data payloads.
    - Web keeps the existing data-only behavior.
    - Native iOS APNs tokens never pass through FCM.
    """

    def __init__(self):
        configured_project_id = getattr(
            settings,
            "FIREBASE_PROJECT_ID",
            None,
        )

        credentials = getattr(
            settings,
            "FIREBASE_CREDENTIALS",
            None,
        )

        credential_project_id = (
            credentials.get("project_id")
            if isinstance(credentials, dict)
            else None
        )

        self.project_id = configured_project_id or credential_project_id

        if not self.project_id:
            logger.error(
                "[FCM] FIREBASE_PROJECT_ID missing"
            )

        self.base_url = (
            "https://fcm.googleapis.com/v1/"
            f"projects/{self.project_id}/messages:send"
        )

    # ------------------------------------------------------------
    # Device resolution
    # ------------------------------------------------------------
    def get_devices_for_user(
        self,
        user,
        *,
        platforms: Optional[set[str]] = None,
    ) -> List[UserDeviceKey]:
        """Return active eligible FCM devices."""
        if not user:
            return []

        allowed_platforms = set(
            FCM_DEVICE_PLATFORMS
        )

        if platforms is not None:
            requested = {
                str(platform).strip().lower()
                for platform in platforms
                if str(platform).strip()
            }

            allowed_platforms &= requested

        if not allowed_platforms:
            return []

        queryset = (
            UserDeviceKey.objects
            .filter(
                user=user,
                is_active=True,
                platform__in=allowed_platforms,
            )
            .filter(
                Q(platform=DEVICE_PLATFORM_WEB)
                | Q(
                    platform=DEVICE_PLATFORM_ANDROID,
                    is_verified=True,
                )
            )
            .exclude(push_token__isnull=True)
            .exclude(push_token__exact="")
            .only(
                "id",
                "platform",
                "push_token",
                "is_verified",
            )
        )

        return list(queryset)

    def get_tokens_for_user(
        self,
        user,
        *,
        platforms: Optional[set[str]] = None,
    ) -> List[str]:
        """Return FCM tokens for eligible devices."""
        return [
            device.push_token
            for device in self.get_devices_for_user(
                user,
                platforms=platforms,
            )
            if device.push_token
        ]

    # ------------------------------------------------------------
    # Android presentation
    # ------------------------------------------------------------

    def _android_channel_id(
        self,
        data: Dict[str, str],
    ) -> str:
        """Pick the stable Android notification channel."""
        notification_type = (
            data.get("notification_type")
            or ""
        ).strip()

        if notification_type in MESSENGER_NOTIFICATION_TYPES:
            return ANDROID_MESSAGE_CHANNEL_ID

        return ANDROID_GENERAL_CHANNEL_ID

    def _build_message(
        self,
        *,
        token: str,
        platform: Optional[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build a platform-aware FCM HTTP v1 message.

        Android receives notification + data so background/killed-state
        delivery can be displayed by the operating system while preserving
        TownLIT routing metadata.

        Web keeps the existing data-only contract.
        """
        base_data: Dict[str, Any] = dict(data or {})

        # Keep these available to foreground/custom handlers as well.
        base_data.setdefault("title", title)
        base_data.setdefault("body", body)

        safe_data = _stringify_dict(base_data)

        message: Dict[str, Any] = {
            "token": token,
            "data": safe_data,
        }

        normalized_platform = (
            platform
            or ""
        ).strip().lower()

        if normalized_platform == "android":
            channel_id = self._android_channel_id(
                safe_data
            )

            message["notification"] = {
                "title": title,
                "body": body,
            }

            message["android"] = {
                "priority": "HIGH",
                "notification": {
                    "channel_id": channel_id,
                },
            }

        return {
            "message": message,
        }

    # ------------------------------------------------------------
    # FCM error handling
    # ------------------------------------------------------------

    def _parse_fcm_error(
        self,
        response: requests.Response,
    ) -> tuple[Optional[str], Optional[str], str]:
        """
        Return:
        - top-level status
        - FCM-specific error code
        - error message
        """
        try:
            payload = response.json()
        except Exception:
            return None, None, response.text[:1000]

        error = payload.get("error") or {}

        status = error.get("status")
        message = str(
            error.get("message")
            or ""
        )

        fcm_error_code = None

        for detail in error.get("details") or []:
            if not isinstance(detail, dict):
                continue

            if detail.get("@type") == FCM_ERROR_DETAIL_TYPE:
                fcm_error_code = detail.get(
                    "errorCode"
                )
                break

        return (
            str(status) if status else None,
            str(fcm_error_code) if fcm_error_code else None,
            message,
        )

    def _should_retire_token(
        self,
        response: requests.Response,
    ) -> bool:
        """
        Detect token-specific permanent failures.

        INVALID_ARGUMENT is retired only when Firebase identifies it as an
        FCM registration-token error, not for generic malformed payloads.
        """
        status, fcm_error_code, _ = self._parse_fcm_error(
            response
        )

        if (
            response.status_code == 404
            and (
                status == "UNREGISTERED"
                or fcm_error_code == "UNREGISTERED"
            )
        ):
            return True

        if (
            response.status_code == 400
            and status == "INVALID_ARGUMENT"
            and fcm_error_code == "INVALID_ARGUMENT"
        ):
            return True

        return False

    def _retire_device(
        self,
        *,
        device_id: Optional[int],
        token: str,
        platform: Optional[str],
        reason: str,
    ) -> None:
        """
        Retire only the invalid push registration.

        UserDeviceKey is also a canonical encryption device identity.
        An invalid FCM token must never deactivate the whole device.
        """
        try:
            queryset = UserDeviceKey.objects.filter(
                is_active=True,
                push_token=token,
            )

            if device_id is not None:
                queryset = queryset.filter(
                    pk=device_id,
                )
            elif platform:
                queryset = queryset.filter(
                    platform=platform,
                )

            updated = queryset.update(
                push_token=None,
            )

            if updated:
                logger.info(
                    "[FCM] Push registration retired "
                    "device=%s platform=%s reason=%s",
                    device_id,
                    platform,
                    reason,
                )

        except Exception:
            logger.warning(
                "[FCM] Failed to retire push registration "
                "device=%s platform=%s",
                device_id,
                platform,
                exc_info=True,
            )

    # ------------------------------------------------------------
    # HTTP delivery
    # ------------------------------------------------------------

    def _post_payload(
        self,
        *,
        payload: Dict[str, Any],
        access_token: str,
    ) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }

        return requests.post(
            self.base_url,
            json=payload,
            headers=headers,
            timeout=10,
        )

    def _send_to_token(
        self,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        platform: Optional[str] = None,
        device_id: Optional[int] = None,
    ) -> bool:
        """Send one platform-aware FCM message."""
        if not self.project_id:
            logger.error(
                "[FCM] Cannot send push: FIREBASE_PROJECT_ID missing"
            )
            return False

        token = (token or "").strip()

        if not token:
            return False

        payload = self._build_message(
            token=token,
            platform=platform,
            title=title,
            body=body,
            data=data,
        )

        try:
            access_token = get_google_access_token()

            response = self._post_payload(
                payload=payload,
                access_token=access_token,
            )

            # Refresh OAuth once when the provider token was rejected.
            if response.status_code == 401:
                reset_google_access_token_cache()

                response = self._post_payload(
                    payload=payload,
                    access_token=get_google_access_token(),
                )

            if 200 <= response.status_code < 300:
                logger.info(
                    "[FCM] Push sent device=%s platform=%s",
                    device_id,
                    platform,
                )
                return True

            status, fcm_error_code, error_message = (
                self._parse_fcm_error(response)
            )

            logger.warning(
                "[FCM] Push failed device=%s platform=%s "
                "http=%s status=%s fcm_error=%s message=%s",
                device_id,
                platform,
                response.status_code,
                status,
                fcm_error_code,
                error_message[:500],
            )

            if self._should_retire_token(response):
                self._retire_device(
                    device_id=device_id,
                    token=token,
                    platform=platform,
                    reason=fcm_error_code or status or "invalid_token",
                )

            return False

        except Exception as error:
            logger.exception(
                "[FCM] Delivery exception device=%s platform=%s error=%s",
                device_id,
                platform,
                error,
            )
            return False

    # ------------------------------------------------------------
    # Public delivery API
    # ------------------------------------------------------------

    def send_to_tokens(
        self,
        tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        platform: Optional[str] = None,
    ) -> int:
        """
        Send to raw FCM tokens.

        platform=None preserves legacy data-only behavior.
        """
        if not tokens:
            return 0

        sent_count = 0

        for token in tokens:
            if self._send_to_token(
                token,
                title,
                body,
                data,
                platform=platform,
            ):
                sent_count += 1

        return sent_count

    def send_to_user(
        self,
        user,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        platforms: Optional[set[str]] = None,
    ) -> int:
        """Send to eligible FCM devices for a user."""
        devices = self.get_devices_for_user(
            user,
            platforms=platforms,
        )

        if not devices:
            return 0

        sent_count = 0

        for device in devices:
            if self._send_to_token(
                device.push_token,
                title,
                body,
                data or {},
                platform=getattr(
                    device,
                    "platform",
                    None,
                ),
                device_id=getattr(
                    device,
                    "id",
                    None,
                ),
            ):
                sent_count += 1

        return sent_count

push_engine = FirebasePushEngine()