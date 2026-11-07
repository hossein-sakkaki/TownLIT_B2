# apps/core/crypto/field_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Versioned, row-bound field protection using the existing Fernet primitive.

This module does not change legacy Fernet, django_cryptography, or E2EE data.
It implements cryptographic storage only; callers own authorization and masking.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from collections.abc import Mapping

from cryptography.fernet import Fernet, InvalidToken


_ENVELOPE_PREFIX = "tdp1"
_PAYLOAD_PREFIX = b"TownLIT.FieldProtection.v1\x00"
_KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
_FIELD_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.]{0,159}$")
_KEYRING_ENV = "TOWNLIT_DP_FERNET_KEYS_JSON"
_ACTIVE_KEY_ENV = "TOWNLIT_DP_ACTIVE_KEY_ID"


class FieldProtectionError(Exception):
    """Base class for errors that must not contain field contents or secrets."""


class FieldProtectionConfigError(FieldProtectionError):
    pass


class FieldProtectionUnavailable(FieldProtectionError):
    pass


class FieldProtectionIntegrityError(FieldProtectionError):
    pass


class FieldProtector:
    """Encrypt and decrypt text bound to a specific model field and row ID."""

    def __init__(self, *, keys: Mapping[str, str | bytes], active_key_id: str):
        if not isinstance(keys, Mapping) or not keys:
            raise FieldProtectionConfigError("Field protection keyring is not configured.")
        if not isinstance(active_key_id, str) or not _KEY_ID_PATTERN.fullmatch(active_key_id):
            raise FieldProtectionConfigError("Invalid active field protection key ID.")

        ciphers: dict[str, Fernet] = {}
        for key_id, key in keys.items():
            if not isinstance(key_id, str) or not _KEY_ID_PATTERN.fullmatch(key_id):
                raise FieldProtectionConfigError("Invalid field protection key ID.")
            if not isinstance(key, (str, bytes)):
                raise FieldProtectionConfigError("Invalid field protection key configuration.")
            try:
                ciphers[key_id] = Fernet(key.encode("ascii") if isinstance(key, str) else key)
            except (TypeError, ValueError, UnicodeError) as exc:
                raise FieldProtectionConfigError("Invalid field protection key configuration.") from exc

        if active_key_id not in ciphers:
            raise FieldProtectionConfigError("Active field protection key is missing.")
        self._ciphers = ciphers
        self.active_key_id = active_key_id

    @classmethod
    def from_environment(cls) -> "FieldProtector":
        """Load keys at runtime; never fall back to SECRET_KEY or FERNET_KEY."""
        raw_keyring = os.environ.get(_KEYRING_ENV)
        active_key_id = os.environ.get(_ACTIVE_KEY_ENV)
        if not raw_keyring or not active_key_id:
            raise FieldProtectionUnavailable("Field protection keys are unavailable.")
        try:
            keys = json.loads(raw_keyring)
        except (TypeError, ValueError) as exc:
            raise FieldProtectionConfigError("Field protection keyring has invalid structure.") from exc
        if not isinstance(keys, dict):
            raise FieldProtectionConfigError("Field protection keyring has invalid structure.")
        return cls(keys=keys, active_key_id=active_key_id)

    @staticmethod
    def _context(field: str, row_id: int, key_id: str) -> bytes:
        if not isinstance(field, str) or not _FIELD_PATTERN.fullmatch(field):
            raise ValueError("Invalid protected field identifier.")
        if type(row_id) is not int or row_id < 1:
            raise ValueError("A persisted positive row ID is required for protection.")
        return f"{field}:{row_id}:{key_id}".encode("ascii")

    def protect(self, plaintext: str | None, *, field: str, row_id: int) -> str | None:
        context = self._context(field, row_id, self.active_key_id)
        if plaintext is None:
            return None
        if not isinstance(plaintext, str):
            raise TypeError("Field protection accepts strings or None.")
        if len(context) > 65535:
            raise ValueError("Protected field context is too long.")

        payload = (
            _PAYLOAD_PREFIX
            + len(context).to_bytes(2, "big")
            + context
            + plaintext.encode("utf-8")
        )
        token = self._ciphers[self.active_key_id].encrypt(payload).decode("ascii")
        return f"{_ENVELOPE_PREFIX}:{self.active_key_id}:{token}"

    def reveal(self, envelope: str | None, *, field: str, row_id: int) -> str | None:
        self._context(field, row_id, self.active_key_id)
        if envelope is None:
            return None
        if not isinstance(envelope, str):
            raise FieldProtectionIntegrityError("Protected field is invalid.")

        parts = envelope.split(":", 2)
        if len(parts) != 3 or parts[0] != _ENVELOPE_PREFIX:
            raise FieldProtectionIntegrityError("Protected field has an unsupported format.")
        key_id, encoded_token = parts[1], parts[2]
        if not _KEY_ID_PATTERN.fullmatch(key_id) or not encoded_token:
            raise FieldProtectionIntegrityError("Protected field is invalid.")
        cipher = self._ciphers.get(key_id)
        if cipher is None:
            raise FieldProtectionUnavailable("Required field protection key is unavailable.")
        context = self._context(field, row_id, key_id)

        try:
            payload = cipher.decrypt(encoded_token.encode("ascii"))
        except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
            raise FieldProtectionIntegrityError("Protected field failed integrity verification.") from exc

        if not payload.startswith(_PAYLOAD_PREFIX):
            raise FieldProtectionIntegrityError("Protected field failed context verification.")
        offset = len(_PAYLOAD_PREFIX)
        if len(payload) < offset + 2:
            raise FieldProtectionIntegrityError("Protected field failed context verification.")
        stored_length = int.from_bytes(payload[offset:offset + 2], "big")
        offset += 2
        if len(payload) < offset + stored_length:
            raise FieldProtectionIntegrityError("Protected field failed context verification.")
        stored_context = payload[offset:offset + stored_length]
        if not hmac.compare_digest(stored_context, context):
            raise FieldProtectionIntegrityError("Protected field failed context verification.")
        try:
            return payload[offset + stored_length:].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FieldProtectionIntegrityError("Protected field failed integrity verification.") from exc

    def rewrap(self, envelope: str, *, field: str, row_id: int) -> str:
        """Re-encrypt under the active key; retain old keys for historical reads."""
        value = self.reveal(envelope, field=field, row_id=row_id)
        if value is None:
            raise ValueError("Cannot rewrap a null protected field.")
        result = self.protect(value, field=field, row_id=row_id)
        assert result is not None
        return result
