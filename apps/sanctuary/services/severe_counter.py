# apps/sanctuary/services/severe_counter.py

from __future__ import annotations

from django.db.models import Q

from apps.sanctuary.constants.states import (
    PENDING,
    UNDER_REVIEW,
)
from apps.sanctuary.models import (
    SanctuaryRequest,
)
from apps.sanctuary.services.decision_engine import (
    admin_fast_track_reason_codes,
)


def resolve_active_severe_request_count(
    *,
    request_type: str,
    content_type,
    object_id: int,
) -> int:
    """
    Count active Sanctuary requests for a target that include at least
    one admin fast-track reason.

    PostgreSQL JSONField list containment is used because Sanctuary
    reasons are stored as a JSON array.
    """
    severe_reasons = (
        admin_fast_track_reason_codes(
            request_type
        )
    )

    if not severe_reasons:
        return 0

    reason_query = Q()

    for reason in sorted(severe_reasons):
        reason_query |= Q(
            reasons__contains=[reason]
        )

    return (
        SanctuaryRequest.objects
        .filter(
            request_type=request_type,
            content_type=content_type,
            object_id=object_id,
            status__in=[
                PENDING,
                UNDER_REVIEW,
            ],
        )
        .filter(reason_query)
        .count()
    )