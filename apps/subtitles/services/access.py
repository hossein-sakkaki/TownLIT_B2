# apps/subtitles/services/access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

from __future__ import annotations

import logging

from apps.core.boundaries.query import BoundaryVisibilityQuery
from apps.core.visibility.policy import VisibilityPolicy
from apps.core.visibility.query import VisibilityQuery
from apps.organization_content.services.access import can_view_organization_content
from apps.sanctuary.services.held_content_access import held_representation_or_none
from apps.subtitles.models import TranscriptJobStatus
from apps.subtitles.services.testimony_enforcement import (
    is_testimony_review_approved_for_display,
)

logger = logging.getLogger(__name__)

_POST_MODELS = frozenset({"posts.testimony", "posts.moment", "posts.prayer"})
_ORGANIZATION_TEACHING = "organization_media.churchteachingcontent"


def can_view_transcript(*, transcript, viewer) -> bool:
    """Match the underlying media access gate before revealing derived tracks."""
    try:
        if transcript is None or transcript.status != TranscriptJobStatus.DONE:
            return False

        target = transcript.content_object
        if target is None or not getattr(target, "pk", None):
            return False

        label = target._meta.label_lower
        if label in _POST_MODELS:
            return _can_view_post(target=target, viewer=viewer, label=label)

        if label == _ORGANIZATION_TEACHING:
            return _can_view_organization_teaching(target=target, viewer=viewer)

        return False
    except Exception:
        logger.exception(
            "subtitle_access_gate_failed transcript_id=%s",
            getattr(transcript, "pk", None),
        )
        return False


def _can_view_post(*, target, viewer, label: str) -> bool:
    if (
        getattr(target, "is_active", True) is not True
        or getattr(target, "is_suspended", False)
        or getattr(target, "is_hidden", False)
        or getattr(target, "is_converted", False) is not True
    ):
        return False

    if label in {"posts.moment", "posts.prayer"} and not getattr(target, "video", None):
        return False

    if label == "posts.testimony":
        if getattr(target, "type", "") != getattr(target, "TYPE_VIDEO", "video"):
            return False
        if not is_testimony_review_approved_for_display(target):
            return False

    visible = VisibilityQuery.for_viewer(
        viewer=viewer,
        base_queryset=type(target).objects.filter(pk=target.pk),
    )
    visible = BoundaryVisibilityQuery.exclude_boundary_conflicts(
        visible,
        viewer=viewer,
    )
    if not visible.exists():
        return False

    if VisibilityPolicy.gate_reason(viewer=viewer, obj=target):
        return False

    result = held_representation_or_none(
        target=target,
        viewer=viewer if getattr(viewer, "is_authenticated", False) else None,
        data={"id": target.pk},
    )
    return result is not None


def _can_view_organization_teaching(*, target, viewer) -> bool:
    # Published Organization teaching has its own ownership and visibility rules.
    if (
        getattr(target, "content_format", None) != "video"
        or getattr(target, "status", None) != "published"
        or getattr(target, "is_converted", False) is not True
        or not getattr(target, "video", None)
    ):
        return False

    organization = getattr(target, "organization", None)
    if organization is None:
        return False

    return bool(
        can_view_organization_content(organization=organization, viewer=viewer)
    )
