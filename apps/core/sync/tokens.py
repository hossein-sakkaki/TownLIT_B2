# apps/core/sync/tokens.py

from django.utils import timezone
from django.utils.dateparse import parse_datetime


def now_sync_token() -> str:
    """
    Return a server-generated timestamp token.
    """

    return timezone.now().isoformat()


def parse_sync_token(raw: str | None):
    """
    Parse a timestamp-based sync token.

    Returns None for missing/invalid tokens.
    """

    if not raw:
        return None

    value = str(raw).strip()

    if not value:
        return None

    parsed = parse_datetime(value)

    if parsed is None: 
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(
            parsed,
            timezone=timezone.utc,
        )

    return parsed


def sync_token_from_request(request, *, query_key: str = "since"):
    """
    Read sync token from query params first, then header.
    """

    raw = request.query_params.get(query_key)

    if not raw:
        raw = request.headers.get("X-TownLIT-Sync-Token")

    return parse_sync_token(raw)