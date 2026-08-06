# apps/sanctuary/services/counter.py

from __future__ import annotations

from typing import Optional

from django.contrib.contenttypes.models import (
    ContentType,
)

from apps.sanctuary.constants.states import (
    PENDING,
    UNDER_REVIEW,
)
from apps.sanctuary.constants.thresholds import (
    COUNCIL_THRESHOLD,
)
from apps.sanctuary.models import (
    SanctuaryRequest,
)


def get_sanctuary_counter(
    *,
    user,
    request_type: str,
    content_type_str: str,
    object_id: int,
    expose_internal_counts: bool = False,
) -> dict:
    """
    Return Sanctuary state for one target.

    Privacy rules:
    - The caller's own request state may always be returned.
    - Active aggregate count and internal threshold are returned only
      when expose_internal_counts=True.
    """
    normalized_request_type = str(
        request_type or ""
    ).strip()

    normalized_content_type = str(
        content_type_str or ""
    ).strip().lower()

    try:
        app_label, model = (
            normalized_content_type.split(
                ".",
                1,
            )
        )

        content_type = ContentType.objects.get(
            app_label__iexact=app_label,
            model__iexact=model,
        )
    except (
        ValueError,
        ContentType.DoesNotExist,
        ContentType.MultipleObjectsReturned,
    ):
        raise ValueError(
            "Invalid content_type"
        )

    try:
        normalized_object_id = int(
            object_id
        )
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Invalid object_id"
        )

    if normalized_object_id <= 0:
        raise ValueError(
            "Invalid object_id"
        )

    threshold = COUNCIL_THRESHOLD.get(
        normalized_request_type
    )

    if threshold is None:
        raise ValueError(
            "Invalid request_type"
        )

    active_requests = (
        SanctuaryRequest.objects
        .filter(
            request_type=normalized_request_type,
            content_type=content_type,
            object_id=normalized_object_id,
            status__in=[
                PENDING,
                UNDER_REVIEW,
            ],
        )
    )

    user_request: Optional[
        SanctuaryRequest
    ] = None

    if (
        user
        and getattr(
            user,
            "is_authenticated",
            False,
        )
    ):
        user_request = (
            active_requests
            .filter(
                requester=user
            )
            .only("id")
            .order_by("-created_at")
            .first()
        )

    if expose_internal_counts:
        active_count = (
            active_requests.count()
        )

        exposed_threshold = int(
            threshold
        )
    else:
        active_count = 0
        exposed_threshold = 0

    return {
        "request_type": normalized_request_type,
        "content_type": (
            f"{content_type.app_label.lower()}."
            f"{content_type.model.lower()}"
        ),
        "object_id": normalized_object_id,
        "count": active_count,
        "threshold": exposed_threshold,
        "has_reported": bool(
            user_request
        ),
        "request_id": (
            user_request.id
            if user_request
            else None
        ),
    }