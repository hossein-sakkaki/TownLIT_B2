from apps.sanctuary.models import SanctuaryRequest
from apps.sanctuary.constants.states import PENDING, UNDER_REVIEW

def resolve_active_report_count(
    *,
    request_type: str,
    content_type: str,
    object_id: int,
) -> int:
    """
    Count active Sanctuary requests for the same target.
    This is the ONLY number allowed for UI counters.
    """
    return (
        SanctuaryRequest.objects.filter(
            request_type=request_type,
            content_type=content_type,
            object_id=object_id,
            status__in=[PENDING, UNDER_REVIEW],
        )
        .count()
    )
