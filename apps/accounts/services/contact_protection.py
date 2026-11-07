# apps/accounts/services/contact_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Purpose-separated blind lookups and row-bound private contact storage.

Email remains a concrete legacy authentication field during this wave.
No blind index is a password, an encryption key, or a substitute for authorization.
"""
from __future__ import annotations

import hmac

from apps.core.crypto.blind_index import BlindIndexer, BlindIndexConfigError
from apps.core.crypto.protected_columns import protect_column, reveal_column

EMAIL_PURPOSE = "accounts.CustomUser.email"
PHONE_PURPOSE = "accounts.CustomUser.mobile_number"


def normalized_contact(value, *, field):
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("Contact values must be strings or None.")
    normalized = value.strip()
    if not normalized:
        return None
    if field == "email":
        # Preserve existing app semantics: case-insensitive comparisons,
        # not provider-specific dot/plus folding.
        return normalized.casefold()
    if field == "mobile_number":
        # Exact normalized equality, not E.164 equivalence. Do not merge
        # local/international phone representations without a policy.
        return normalized
    raise ValueError("Unknown protected contact field.")


def blind_index(value, *, field):
    normalized = normalized_contact(value, field=field)
    if normalized is None:
        return None
    purpose = EMAIL_PURPOSE if field == "email" else PHONE_PURPOSE
    return BlindIndexer.from_environment().digest(normalized, purpose=purpose)


def index_matches(stored, value, *, field):
    normalized = normalized_contact(value, field=field)
    if stored is None or normalized is None:
        return stored is None and normalized is None
    if not isinstance(stored, str):
        return False
    parts = stored.split(":", 2)
    if len(parts) != 3 or parts[0] != "bi1":
        return False
    purpose = EMAIL_PURPOSE if field == "email" else PHONE_PURPOSE
    try:
        expected = BlindIndexer.from_environment().digest(
            normalized, purpose=purpose, key_id=parts[1],
        )
    except (BlindIndexConfigError, ValueError, TypeError):
        return False
    return hmac.compare_digest(stored, expected)


def encrypt_contact(user, value, *, field):
    return protect_column(user, field, value, "text")


def decrypt_contact(user, ciphertext, *, field):
    return reveal_column(user, field, ciphertext, "text")
