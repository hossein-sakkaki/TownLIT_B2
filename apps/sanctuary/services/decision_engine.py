# apps/sanctuary/services/decision_engine.py

from apps.sanctuary.constants.thresholds import (
    COUNCIL_THRESHOLD,
    ADMIN_FAST_TRACK_THRESHOLD,
)

# ------------------------------------------------------------
# Decision helpers for Sanctuary workflow
# ------------------------------------------------------------
def should_admin_fast_track(target_type: str, report_count: int) -> bool:
    """
    Returns True if the case must go directly to admin
    without council review.
    """
    threshold = ADMIN_FAST_TRACK_THRESHOLD.get(target_type)
    if threshold is None:
        return False
    return report_count >= threshold


def should_form_council(target_type: str, report_count: int) -> bool:
    """
    Returns True if enough reports exist
    to form a Sanctuary council.
    """
    threshold = COUNCIL_THRESHOLD.get(target_type)
    if threshold is None:
        return False
    return report_count >= threshold


def is_monitor_only(target_type: str, report_count: int) -> bool:
    """
    Returns True if the case should only be monitored.
    Not enough reports for council or admin action.
    """
    admin_threshold = ADMIN_FAST_TRACK_THRESHOLD.get(target_type)
    council_threshold = COUNCIL_THRESHOLD.get(target_type)

    # No thresholds defined → always monitor
    if admin_threshold is None and council_threshold is None:
        return True

    # Below both thresholds → monitor only
    min_threshold = min(
        t for t in [admin_threshold, council_threshold] if t is not None
    )
    return report_count < min_threshold
