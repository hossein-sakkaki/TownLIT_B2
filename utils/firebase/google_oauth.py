# utils/firebase/google_oauth.py

import time
import json
from typing import Optional
from cryptography.hazmat.primitives import serialization


import jwt  # PyJWT
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
FIREBASE_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"

# Module-level cache
_cached_access_token: Optional[str] = None
_cached_expires_at: float = 0.0


def _load_service_account() -> dict:
    creds = settings.FIREBASE_CREDENTIALS
    if not creds:
        raise ImproperlyConfigured("Firebase service account credentials not configured.")
    return creds


# Build and sign JWT ----------------------------------------------------------------------
def _build_jwt(creds: dict) -> str:
    now = int(time.time())

    payload = {
        "iss": creds["client_email"],
        "scope": FIREBASE_SCOPE,
        "aud": creds["token_uri"],
        "iat": now,
        "exp": now + 3600,
    }

    # ------------------------------------------------------------------
    # 🔥 FIX #1 — Convert all escaped newlines to real newlines
    # ------------------------------------------------------------------
    raw_key = creds["private_key"]

    # Remove accidental whitespace or BOM
    raw_key = raw_key.strip()

    # Replace \n with real newlines (VERY important)
    raw_key = raw_key.replace("\\n", "\n")

    # Make sure key begins and ends properly
    if not raw_key.startswith("-----BEGIN PRIVATE KEY-----"):
        raise ImproperlyConfigured("Invalid private key format (missing header)")
    if not raw_key.endswith("-----END PRIVATE KEY-----"):
        raise ImproperlyConfigured("Invalid private key format (missing footer)")

    # Encode properly
    raw_key_bytes = raw_key.encode("utf-8")

    # ------------------------------------------------------------------
    # 🔥 FIX #2 — Load the PEM key safely
    # ------------------------------------------------------------------
    private_key = serialization.load_pem_private_key(
        raw_key_bytes,
        password=None,
    )

    # ------------------------------------------------------------------
    # 🔥 SIGN JWT
    # ------------------------------------------------------------------
    jwt_token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
    )

    return jwt_token




def _fetch_access_token(creds: dict) -> tuple[str, float]:
    """
    Exchange signed JWT for access token from Google OAuth.
    """
    assertion = _build_jwt(creds)
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }
    resp = requests.post(creds.get("token_uri", GOOGLE_OAUTH_TOKEN_URL), data=data, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]
    expires_in = int(payload.get("expires_in", 3600))
    expires_at = time.time() + expires_in - 60  # subtract small buffer
    return access_token, expires_at


def get_google_access_token() -> str:
    """
    Get cached Google access token or fetch a new one.
    """
    global _cached_access_token, _cached_expires_at

    now = time.time()
    if _cached_access_token and now < _cached_expires_at:
        return _cached_access_token

    creds = _load_service_account()
    access_token, expires_at = _fetch_access_token(creds)

    _cached_access_token = access_token
    _cached_expires_at = expires_at
    return access_token
