# apps/core/sync/responses.py

from django.utils import timezone


def build_sync_response(
    *,
    items=None,
    updated_items=None,
    deleted_ids=None,
    removed_ids=None,
    next_sync_token=None,
    has_more=False,
    extra=None,
) -> dict:
    """
    Build a stable sync response shared by all domains.
    """

    server_time = timezone.now().isoformat()

    payload = {
        "items": items or [],
        "updated_items": updated_items or [],
        "deleted_ids": deleted_ids or [],
        "removed_ids": removed_ids or [],
        "next_sync_token": next_sync_token or server_time,
        "server_time": server_time,
        "has_more": bool(has_more),
    }

    if extra:
        payload.update(extra)

    return payload


def build_empty_sync_response(
    *,
    next_sync_token=None,
) -> dict:
    """
    Build an empty successful sync response.
    """

    return build_sync_response(
        next_sync_token=next_sync_token,
    ) 