# apps/sanctuary/services/counter.py
# ============================================================
# Sanctuary Counter Service
# ============================================================

from typing import Optional
from django.contrib.contenttypes.models import ContentType
from apps.sanctuary.models import SanctuaryRequest
from apps.sanctuary.constants.thresholds import COUNCIL_THRESHOLD


def get_sanctuary_counter(
    *,
    user,
    request_type: str,
    content_type_str: str,
    object_id: int,
) -> dict:
    """
    Returns sanctuary counter info for a given target.
    """

    # Resolve ContentType
    try:
        app_label, model = content_type_str.split(".")
        ct = ContentType.objects.get(app_label=app_label, model=model)
    except Exception:
        raise ValueError("Invalid content_type")

    # All active requests for this target
    qs = SanctuaryRequest.objects.filter(
        request_type=request_type,
        content_type=ct,
        object_id=object_id,
    )

    count = qs.count()

    # Has this user already reported?
    user_request: Optional[SanctuaryRequest] = qs.filter(
        requester=user
    ).only("id").first()

    threshold = COUNCIL_THRESHOLD.get(request_type)

    if threshold is None:
        raise ValueError("Invalid request_type")

    return {
        "request_type": request_type,
        "content_type": content_type_str,
        "object_id": object_id,

        "count": count,
        "threshold": threshold,

        "has_reported": bool(user_request),
        "request_id": user_request.id if user_request else None,
    }
