from apps.sanctuary.constants.thresholds import (
    COUNCIL_THRESHOLD,
    ADMIN_FAST_TRACK_THRESHOLD,
)

def resolve_ui_threshold(request_type: str) -> int:
    """
    Threshold shown in UI counters.
    Always uses council threshold.
    """
    return int(COUNCIL_THRESHOLD.get(request_type, 0))


def resolve_admin_threshold(request_type: str) -> int:
    """
    Threshold used ONLY for routing / escalation.
    """
    return int(ADMIN_FAST_TRACK_THRESHOLD.get(request_type, 0))
