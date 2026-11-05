# apps/accounts/services/password_reset_tokens.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-05.
# Last Update by Hossein Sakkaki on 2026-11-05.
#

"""Password reset bearer generation and stored-verifier compatibility.

V2 reset tokens have 256 random bits. SHA-256 is appropriate for their
high-entropy verifiers; this is not a blind-index scheme for emails or phones.
No database schema or new encryption key is needed.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets


_V2_BEARER_PREFIX = "r2_"
_V2_STORED_PREFIX = "pwreset:v2:sha256:"
_V2_TOKEN_RE = re.compile(r"r2_[A-Za-z0-9_-]{43}\Z")
_LEGACY_TOKEN_RE = re.compile(r"g[A-Za-z0-9_-]{25,253}={0,2}\Z")


def should_issue_password_reset_token_v2() -> bool:
    """Use only after every backend instance can consume both token formats.

    Feature switch belongs in backend process environment; default is legacy
    issuance to make mixed-version rollout safe. Never enable for old readers.
    """
    return os.environ.get(
        "PASSWORD_RESET_TOKEN_V2_ISSUE", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}


def issue_password_reset_token_v2() -> tuple[str, str]:
    """Return a URL-safe bearer and its non-reversible stored verifier."""
    bearer = _V2_BEARER_PREFIX + secrets.token_urlsafe(32)
    digest = hashlib.sha256(bearer.encode("ascii")).hexdigest()
    return bearer, _V2_STORED_PREFIX + digest


def password_reset_lookup_value(bearer: str) -> str | None:
    """Resolve V2 bearer into a verifier, or accept existing Fernet links.

    This does not decrypt or derive a legacy Fernet token. Legacy token lookup
    uses exact match only and ends after its stored expiration time.
    """
    if not isinstance(bearer, str) or len(bearer) > 255:
        return None
    if _V2_TOKEN_RE.fullmatch(bearer):
        return _V2_STORED_PREFIX + hashlib.sha256(
            bearer.encode("ascii")
        ).hexdigest()
    if _LEGACY_TOKEN_RE.fullmatch(bearer):
        return bearer
    return None
