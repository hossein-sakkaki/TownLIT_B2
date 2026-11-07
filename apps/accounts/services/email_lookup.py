# apps/accounts/services/email_lookup.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Exact email and login-identifier lookups on the existing blind index.

This service intentionally never falls back to a plaintext email lookup.
Only user email equality is handled here; external contact/invite records have
separate storage contracts and are outside the CustomUser email domain.

CustomUser.email is a Python property backed only by authenticated encrypted
storage, and email equality queries use the indexed HMAC digest. The concrete
Django USERNAME_FIELD is username, not email.
"""

from __future__ import annotations

from django.db.models import Q

from apps.accounts.services.contact_protection import blind_index, normalized_contact


def user_email_index(value: str | None) -> str | None:
    """Derive the unique equality index or return None for a blank input.

    A blank value must never resolve to the SQL NULL bucket, because legacy
    users may have a NULL email_blind_index before backfill verification.
    """
    if not isinstance(value, str):
        return None
    normalized = normalized_contact(value, field="email")
    if normalized is None:
        return None
    return blind_index(normalized, field="email")


def user_email_q(value: str | None) -> Q:
    """Build a fail-closed equality predicate for CustomUser.

    The HMAC key is required for real email lookups. Never silently revert to
    SQL matching on the legacy plaintext email column.
    """
    index = user_email_index(value)
    if index is None:
        return Q(pk__in=[])
    return Q(email_blind_index=index)


def user_identifier_q(identifier: str | None) -> Q:
    """Resolve exact email or case-insensitive username without email scans."""
    if not isinstance(identifier, str):
        return Q(pk__in=[])
    normalized = identifier.strip()
    if not normalized:
        return Q(pk__in=[])
    query = Q(username__iexact=normalized)
    if "@" in normalized:
        query |= user_email_q(normalized)
    return query
