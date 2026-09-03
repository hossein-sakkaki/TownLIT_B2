# utils/firebase/google_oauth.py

import json
import threading
import time
from typing import Optional

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
FIREBASE_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

_cached_access_token: Optional[str] = None
_cached_expires_at: float = 0.0
_cache_lock = threading.Lock()


def _load_service_account() -> dict:
    """Load and validate Firebase service account credentials."""
    credentials = getattr(
        settings,
        "FIREBASE_CREDENTIALS",
        None,
    )

    if not credentials:
        raise ImproperlyConfigured(
            "Firebase service account credentials are not configured."
        )

    if isinstance(credentials, str):
        try:
            credentials = json.loads(
                credentials
            )
        except json.JSONDecodeError as error:
            raise ImproperlyConfigured(
                "FIREBASE_CREDENTIALS is not valid JSON."
            ) from error

    if not isinstance(credentials, dict):
        raise ImproperlyConfigured(
            "FIREBASE_CREDENTIALS must be a dictionary or JSON object."
        )

    required_fields = {
        "client_email",
        "private_key",
    }

    missing = sorted(
        field
        for field in required_fields
        if not credentials.get(field)
    )

    if missing:
        raise ImproperlyConfigured(
            "Firebase service account is missing: "
            + ", ".join(missing)
        )

    return credentials


def _load_private_key(creds: dict):
    """Load the service account RSA private key safely."""
    raw_key = str(
        creds.get("private_key")
        or ""
    ).strip()

    raw_key = raw_key.replace(
        "\\n",
        "\n",
    )

    if not raw_key.startswith(
        "-----BEGIN PRIVATE KEY-----"
    ):
        raise ImproperlyConfigured(
            "Invalid Firebase private key format: missing header."
        )

    if not raw_key.endswith(
        "-----END PRIVATE KEY-----"
    ):
        raise ImproperlyConfigured(
            "Invalid Firebase private key format: missing footer."
        )

    try:
        return serialization.load_pem_private_key(
            raw_key.encode("utf-8"),
            password=None,
        )

    except Exception as error:
        raise ImproperlyConfigured(
            "Firebase private key could not be loaded."
        ) from error


def _build_jwt(creds: dict) -> str:
    """Build the signed OAuth service-account JWT."""
    now = int(
        time.time()
    )

    token_uri = (
        creds.get("token_uri")
        or GOOGLE_OAUTH_TOKEN_URL
    )

    payload = {
        "iss": creds["client_email"],
        "scope": FIREBASE_SCOPE,
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }

    private_key = _load_private_key(
        creds
    )

    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
    )


def _fetch_access_token(
    creds: dict,
) -> tuple[str, float]:
    """Exchange the signed JWT for a Google OAuth access token."""
    token_uri = (
        creds.get("token_uri")
        or GOOGLE_OAUTH_TOKEN_URL
    )

    response = requests.post(
        token_uri,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": _build_jwt(creds),
        },
        timeout=10,
    )

    response.raise_for_status()

    payload = response.json()

    access_token = payload.get(
        "access_token"
    )

    if not access_token:
        raise RuntimeError(
            "Google OAuth response did not contain an access token."
        )

    expires_in = int(
        payload.get(
            "expires_in",
            3600,
        )
    )

    # Keep a safety margin before actual expiry.
    expires_at = (
        time.time()
        + expires_in
        - 60
    )

    return (
        str(access_token),
        expires_at,
    )


def reset_google_access_token_cache() -> None:
    """Invalidate the cached Google OAuth token."""
    global _cached_access_token
    global _cached_expires_at

    with _cache_lock:
        _cached_access_token = None
        _cached_expires_at = 0.0


def get_google_access_token() -> str:
    """
    Return a cached Google OAuth token or fetch a fresh one.

    The lock prevents multiple Django workers/threads in the same process
    from refreshing the token simultaneously.
    """
    global _cached_access_token
    global _cached_expires_at

    now = time.time()

    if (
        _cached_access_token
        and now < _cached_expires_at
    ):
        return _cached_access_token

    with _cache_lock:
        now = time.time()

        # Another thread may have refreshed it while we waited.
        if (
            _cached_access_token
            and now < _cached_expires_at
        ):
            return _cached_access_token

        credentials = _load_service_account()

        access_token, expires_at = (
            _fetch_access_token(
                credentials
            )
        )

        _cached_access_token = access_token
        _cached_expires_at = expires_at

        return access_token