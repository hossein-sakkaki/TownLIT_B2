# apps/sanctuary/services/decision_engine.py

from __future__ import annotations

from collections.abc import Iterable

from apps.sanctuary.constants.fast_track import (
    ADMIN_FAST_TRACK,
)
from apps.sanctuary.constants.thresholds import (
    ADMIN_FAST_TRACK_THRESHOLD,
    COUNCIL_THRESHOLD,
)


def normalize_reason_codes(
    reasons: Iterable[str] | None,
) -> set[str]:
    """
    Normalize Sanctuary reason codes.

    Empty, non-string, and duplicate values are ignored.
    """
    normalized: set[str] = set()

    for reason in reasons or []:
        if not isinstance(reason, str):
            continue

        clean_reason = reason.strip()

        if clean_reason:
            normalized.add(clean_reason)

    return normalized


def admin_fast_track_reason_codes(
    target_type: str,
) -> set[str]:
    """
    Return reason codes eligible for immediate admin review.
    """
    normalized_target_type = str(
        target_type or ""
    ).strip()

    configured_reasons = ADMIN_FAST_TRACK.get(
        normalized_target_type,
        [],
    )

    return normalize_reason_codes(
        configured_reasons
    )


def matching_admin_fast_track_reasons(
    *,
    target_type: str,
    reasons: Iterable[str] | None,
) -> set[str]:
    """
    Return submitted reasons that qualify for admin fast-track.
    """
    submitted_reasons = normalize_reason_codes(
        reasons
    )

    configured_reasons = (
        admin_fast_track_reason_codes(
            target_type
        )
    )

    return submitted_reasons.intersection(
        configured_reasons
    )


def has_admin_fast_track_reason(
    *,
    target_type: str,
    reasons: Iterable[str] | None,
) -> bool:
    """
    Return True when at least one submitted reason is severe.
    """
    return bool(
        matching_admin_fast_track_reasons(
            target_type=target_type,
            reasons=reasons,
        )
    )


def should_admin_fast_track(
    *,
    target_type: str,
    reasons: Iterable[str] | None,
    severe_request_count: int,
) -> bool:
    """
    Decide whether the current Sanctuary wave must enter admin flow.

    Rules:
    - At least one submitted reason must be configured as severe.
    - The number of active severe requests must reach the configured
      admin threshold for this target type.
    """
    threshold = ADMIN_FAST_TRACK_THRESHOLD.get(
        target_type
    )

    if threshold is None:
        return False

    if not has_admin_fast_track_reason(
        target_type=target_type,
        reasons=reasons,
    ):
        return False

    return max(
        int(severe_request_count or 0),
        0,
    ) >= int(threshold)


def should_form_council(
    target_type: str,
    active_request_count: int,
) -> bool:
    """
    Return True when the active Sanctuary wave reaches the council
    threshold for this target type.
    """
    threshold = COUNCIL_THRESHOLD.get(
        target_type
    )

    if threshold is None:
        return False

    return max(
        int(active_request_count or 0),
        0,
    ) >= int(threshold)


def is_monitor_only(
    *,
    target_type: str,
    reasons: Iterable[str] | None,
    active_request_count: int,
    severe_request_count: int,
) -> bool:
    """
    Return True when the request has not entered admin or council flow.
    """
    if should_admin_fast_track(
        target_type=target_type,
        reasons=reasons,
        severe_request_count=severe_request_count,
    ):
        return False

    if should_form_council(
        target_type,
        active_request_count,
    ):
        return False

    return True