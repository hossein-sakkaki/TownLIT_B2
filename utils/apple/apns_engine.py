# utils/apple/apns_engine.py

import base64
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from django.conf import settings
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as crypto_utils

from apps.accounts.models.devices import UserDeviceKey

logger = logging.getLogger(__name__)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class APNsConfig:
    enabled: bool
    key_id: str
    team_id: str
    topic: str
    auth_key_path: str
    use_sandbox: bool

    @property
    def host(self) -> str:
        if self.use_sandbox:
            return "https://api.sandbox.push.apple.com"
        return "https://api.push.apple.com"


class APNsEngine:
    """
    Sends native iOS push notifications through Apple APNs.

    Development/Xcode builds require sandbox.
    TestFlight/App Store builds require production.
    """

    def __init__(self) -> None:
        self._cached_jwt: Optional[str] = None
        self._cached_jwt_iat: int = 0

    def _config(self) -> APNsConfig:
        return APNsConfig(
            enabled=getattr(settings, "APNS_ENABLED", False),
            key_id=getattr(settings, "APNS_KEY_ID", ""),
            team_id=getattr(settings, "APNS_TEAM_ID", ""),
            topic=getattr(settings, "APNS_TOPIC", ""),
            auth_key_path=getattr(settings, "APNS_AUTH_KEY_PATH", ""),
            use_sandbox=getattr(settings, "APNS_USE_SANDBOX", True),
        )

    def _jwt(self, config: APNsConfig) -> str:
        """
        APNs JWT can be reused for up to 60 minutes.
        We refresh after 45 minutes.
        """
        now = int(time.time())

        if self._cached_jwt and (now - self._cached_jwt_iat) < 45 * 60:
            return self._cached_jwt

        header = {
            "alg": "ES256",
            "kid": config.key_id,
        }
        claims = {
            "iss": config.team_id,
            "iat": now,
        }

        signing_input = (
            _b64url(json.dumps(header, separators=(",", ":")).encode())
            + "."
            + _b64url(json.dumps(claims, separators=(",", ":")).encode())
        )

        with open(config.auth_key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
            )

        signature_der = private_key.sign(
            signing_input.encode("ascii"),
            ec.ECDSA(hashes.SHA256()),
        )

        r, s = crypto_utils.decode_dss_signature(signature_der)
        signature_raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")

        token = signing_input + "." + _b64url(signature_raw)

        self._cached_jwt = token
        self._cached_jwt_iat = now

        return token

    def send_to_token(
        self,
        *,
        token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        badge: Optional[int] = None,
        sound: str = "default",
    ) -> bool:
        config = self._config()

        if not config.enabled:
            logger.info("[APNs] Disabled; skipping.")
            return False

        missing = []
        if not config.key_id:
            missing.append("APNS_KEY_ID")
        if not config.team_id:
            missing.append("APNS_TEAM_ID")
        if not config.topic:
            missing.append("APNS_TOPIC")
        if not config.auth_key_path:
            missing.append("APNS_AUTH_KEY_PATH")

        if missing:
            logger.warning("[APNs] Missing settings: %s", ", ".join(missing))
            return False

        if not token:
            return False

        aps: Dict[str, Any] = {
            "alert": {
                "title": title,
                "body": body,
            },
            "sound": sound,
        }

        if badge is not None:
            aps["badge"] = badge

        payload: Dict[str, Any] = {
            "aps": aps,
        }

        if data:
            # APNs custom payload values must be JSON-serializable.
            for key, value in data.items():
                payload[str(key)] = "" if value is None else str(value)

        url = f"{config.host}/3/device/{token}"

        headers = {
            "authorization": f"bearer {self._jwt(config)}",
            "apns-topic": config.topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "content-type": "application/json",
        }

        try:
            with httpx.Client(http2=True, timeout=10.0) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

            if response.status_code == 200:
                logger.info(
                    "[APNs] Push sent OK token_prefix=%s sound=%s",
                    token[:12],
                    sound,
                )
                return True

            reason = None
            try:
                reason = response.json().get("reason")
            except Exception:
                reason = response.text

            logger.warning(
                "[APNs] Push failed status=%s reason=%s token_prefix=%s "
                "sandbox=%s host=%s topic=%s sound=%s apns_id=%s response=%s",
                response.status_code,
                reason,
                token[:12],
                config.use_sandbox,
                config.host,
                config.topic,
                sound,
                response.headers.get("apns-id"),
                response.text,
            )

            return False

        except Exception as exc:
            logger.warning(
                "[APNs] Exception while sending push token_prefix=%s sandbox=%s host=%s topic=%s error=%s",
                token[:12],
                config.use_sandbox,
                config.host,
                config.topic,
                exc,
                exc_info=True,
            )
            return False

    def send_to_user(
        self,
        user,
        *,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        badge: Optional[int] = None,
        sound: str = "default",
    ) -> int:
        """
        Send APNs notification to all active verified iOS devices for user.
        Returns number of successful sends.
        """
        devices = UserDeviceKey.objects.filter(
            user=user,
            platform__iexact="ios",
            is_active=True,
            is_verified=True,
            push_token__isnull=False,
        ).exclude(push_token="")

        sent = 0

        for device in devices:
            ok = self.send_to_token(
                token=device.push_token,
                title=title,
                body=body,
                data=data,
                badge=badge,
                sound=sound,
            )

            if ok:
                sent += 1

        return sent


apns_engine = APNsEngine()