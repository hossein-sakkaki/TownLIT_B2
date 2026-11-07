# apps/core/crypto/blind_index.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Versioned, purpose-bound HMAC equality index. Separate from encryption keys.

This primitive is not wired into CustomUser.email, mobile_number or any DB
column yet. Those lookups require a separate full-contract rollout.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping


_KEY_ID = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
_PURPOSE = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,159}$")
_PREFIX = b"TownLIT.BlindIndex.v1\x00"


class BlindIndexConfigError(Exception):
    pass


class BlindIndexer:
    def __init__(self, *, keys: Mapping[str, str | bytes], active_key_id: str):
        if not isinstance(keys, Mapping) or not keys or not isinstance(active_key_id, str) or not _KEY_ID.fullmatch(active_key_id):
            raise BlindIndexConfigError("Invalid blind index configuration.")
        self._keys = {}
        for key_id, encoded in keys.items():
            if not isinstance(key_id, str) or not _KEY_ID.fullmatch(key_id):
                raise BlindIndexConfigError("Invalid blind index key identifier.")
            try:
                raw = base64.urlsafe_b64decode(encoded if isinstance(encoded, bytes) else encoded.encode("ascii"))
            except (ValueError, UnicodeError, TypeError) as exc:
                raise BlindIndexConfigError("Invalid blind index key material.") from exc
            if len(raw) != 32:
                raise BlindIndexConfigError("Blind index keys must contain 32 random bytes.")
            self._keys[key_id] = raw
        if active_key_id not in self._keys:
            raise BlindIndexConfigError("Active blind index key is unavailable.")
        self.active_key_id = active_key_id

    @classmethod
    def from_environment(cls):
        raw = os.environ.get("TOWNLIT_DP_BLIND_INDEX_KEYS_JSON")
        active = os.environ.get("TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID")
        if not raw or not active:
            raise BlindIndexConfigError("Blind index keys are unavailable.")
        try:
            keys = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise BlindIndexConfigError("Invalid blind index configuration.") from exc
        return cls(keys=keys, active_key_id=active)

    def digest(self, value: str, *, purpose: str, key_id: str | None = None) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("A normalized non-empty value is required.")
        if not isinstance(purpose, str) or not _PURPOSE.fullmatch(purpose):
            raise ValueError("Invalid blind index purpose.")
        identifier = key_id or self.active_key_id
        key = self._keys.get(identifier)
        if key is None:
            raise BlindIndexConfigError("Required blind index key is unavailable.")
        body = _PREFIX + purpose.encode("ascii") + b"\x00" + value.encode("utf-8")
        digest = hmac.new(key, body, hashlib.sha256).hexdigest()
        return f"bi1:{identifier}:{digest}"
