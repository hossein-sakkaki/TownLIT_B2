# apps/sanctuary/services/safety_hold.py

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from apps.sanctuary.constants.states import (
    OUTCOME_CONFIRMED,
    OUTCOME_REJECTED,
    PENDING,
    UNDER_REVIEW,
)
from apps.sanctuary.models import SanctuaryOutcome, SanctuaryRequest, SanctuarySafetyHold
from apps.sanctuary.services.decision_engine import (
    admin_fast_track_reason_codes,
    matching_admin_fast_track_reasons,
)

logger = logging.getLogger(__name__)


def _locked_target(content_type, object_id):
    model = content_type.model_class()
    if model is None:
        return None

    try:
        return model._default_manager.select_for_update().filter(pk=object_id).first()
    except Exception:
        logger.exception(
            "[Sanctuary] Failed to lock safety-hold target ct=%s object_id=%s",
            content_type.pk,
            object_id,
        )
        return None


def _merge_reason_codes(current, incoming) -> list[str]:
    values = set()

    for item in list(current or []) + list(incoming or []):
        if isinstance(item, str) and item.strip():
            values.add(item.strip())

    return sorted(values)


def _schedule_comment_visibility_broadcast(target, *, visible: bool) -> None:
    """
    Update open Comment threads after a Sanctuary hold changes visibility.

    Hidden comments use the existing "deleted" event so current clients
    immediately remove them without deleting the database record.

    Restored comments use the existing "created" event so clients can insert
    them again after a rejected Sanctuary outcome.
    """
    try:
        if target._meta.label_lower != "posts.comment":
            return

        comment_id = target.pk
        content_type_id = target.content_type_id
        object_id = target.object_id
        parent_id = target.recomment_id

        ct = target.content_type
        content_type_label = (
            f"{ct.app_label}.{ct.model}"
            if ct
            else None
        )
    except Exception:
        logger.exception(
            "[Sanctuary] Failed to prepare Comment realtime visibility event."
        )
        return

    def _broadcast():
        try:
            from apps.posts.models.comment import Comment
            from apps.posts.serializers.comments import CommentReadSerializer
            from apps.posts.views.comments import (
                _comment_realtime_payload,
                _deleted_comment_realtime_payload,
                _safe_broadcast,
            )

            if visible:
                comment = (
                    Comment.objects
                    .select_related("name", "content_type")
                    .filter(pk=comment_id, is_active=True)
                    .first()
                )

                if comment is None:
                    return

                serialized = CommentReadSerializer(
                    comment,
                    context={},
                ).data

                payload = _comment_realtime_payload(
                    comment,
                    serialized=serialized,
                )

                _safe_broadcast(
                    "created",
                    payload,
                    comment.content_type_id,
                    comment.object_id,
                )
                return

            payload = _deleted_comment_realtime_payload(
                comment_id=comment_id,
                content_type_id=content_type_id,
                content_type_label=content_type_label,
                object_id=object_id,
                parent_id=parent_id,
            )

            _safe_broadcast(
                "deleted",
                payload,
                content_type_id,
                object_id,
            )

        except Exception:
            logger.exception(
                "[Sanctuary] Comment realtime visibility broadcast failed.",
                extra={
                    "comment_id": comment_id,
                    "visible": visible,
                },
            )

    transaction.on_commit(_broadcast)
    
def _remaining_active_severe_requests(outcome: SanctuaryOutcome):
    """
    Return active severe requests for the same target that are not linked
    to the current outcome.
    """
    severe_reasons = admin_fast_track_reason_codes("content")

    if not severe_reasons:
        return SanctuaryRequest.objects.none()

    reason_query = Q()
    for reason in sorted(severe_reasons):
        reason_query |= Q(reasons__contains=[reason])

    linked_request_ids = list(
        outcome.sanctuary_requests.values_list("id", flat=True)
    )

    return (
        SanctuaryRequest.objects
        .filter(
            request_type="content",
            content_type=outcome.content_type,
            object_id=outcome.object_id,
            status__in=[PENDING, UNDER_REVIEW],
        )
        .exclude(id__in=linked_request_ids)
        .filter(reason_query)
    )
    
    
@transaction.atomic
def apply_sanctuary_safety_hold(
    sanctuary_request: SanctuaryRequest,
) -> SanctuarySafetyHold | None:
    """
    Apply or extend a temporary hold for a severe content request.

    Only content requests are supported in this release.
    Account, organization, and Messenger enforcement remain unchanged.
    """
    request_obj = (
        SanctuaryRequest.objects
        .select_for_update()
        .select_related("content_type")
        .get(pk=sanctuary_request.pk)
    )

    if request_obj.request_type != "content":
        return None

    severe_reasons = matching_admin_fast_track_reasons(
        target_type=request_obj.request_type,
        reasons=request_obj.reasons,
    )

    if not severe_reasons:
        return None

    target = _locked_target(request_obj.content_type, request_obj.object_id)
    if target is None:
        return None

    if not hasattr(target, "is_active"):
        logger.warning(
            "[Sanctuary] Safety hold target has no is_active field: %s:%s",
            request_obj.content_type_id,
            request_obj.object_id,
        )
        return None

    existing = (
        SanctuarySafetyHold.objects
        .select_for_update()
        .filter(
            content_type=request_obj.content_type,
            object_id=request_obj.object_id,
            status=SanctuarySafetyHold.STATUS_ACTIVE,
        )
        .first()
    )

    if existing:
        existing.supporting_requests.add(request_obj)

        merged_reasons = _merge_reason_codes(existing.reason_codes, severe_reasons)
        if merged_reasons != existing.reason_codes:
            existing.reason_codes = merged_reasons
            existing.save(update_fields=["reason_codes"])

        return existing

    previous_is_active = bool(getattr(target, "is_active", True))
    previous_is_suspended = bool(getattr(target, "is_suspended", False))
    did_deactivate_target = False

    if previous_is_active:
        updated = target.__class__._default_manager.filter(
            pk=target.pk,
            is_active=True,
        ).update(is_active=False)

        did_deactivate_target = updated > 0
        if did_deactivate_target:
            target.is_active = False

    hold = SanctuarySafetyHold.objects.create(
        request_type=request_obj.request_type,
        content_type=request_obj.content_type,
        object_id=request_obj.object_id,
        trigger_request=request_obj,
        reason_codes=sorted(severe_reasons),
        previous_is_active=previous_is_active,
        previous_is_suspended=previous_is_suspended,
        did_deactivate_target=did_deactivate_target,
    )

    hold.supporting_requests.add(request_obj)

    _schedule_comment_visibility_broadcast(
        target,
        visible=False,
    )

    logger.warning(
        "[Sanctuary] Temporary safety hold applied hold=%s request=%s target=%s:%s deactivated=%s",
        hold.pk,
        request_obj.pk,
        request_obj.content_type_id,
        request_obj.object_id,
        did_deactivate_target,
    )

    return hold


@transaction.atomic
def close_sanctuary_safety_hold(
    outcome: SanctuaryOutcome,
    *,
    ended_by=None,
) -> SanctuarySafetyHold | None:
    """
    Close or retain an active hold after a final outcome.

    Confirmed:
    - Permanent moderation replaces the temporary hold.
    - The target is never reactivated.

    Rejected:
    - The hold is released only when no other active severe request remains.
    - Target state is restored only when this hold originally deactivated it.
    - Unrelated moderation suspension is never removed.
    """
    outcome_obj = (
        SanctuaryOutcome.objects
        .select_for_update()
        .select_related("content_type")
        .get(pk=outcome.pk)
    )

    if outcome_obj.outcome_status not in {OUTCOME_CONFIRMED, OUTCOME_REJECTED}:
        return None

    hold = (
        SanctuarySafetyHold.objects
        .select_for_update()
        .filter(
            content_type=outcome_obj.content_type,
            object_id=outcome_obj.object_id,
            status=SanctuarySafetyHold.STATUS_ACTIVE,
        )
        .first()
    )

    if hold is None:
        return None

    linked_requests = list(outcome_obj.sanctuary_requests.all())
    if linked_requests:
        hold.supporting_requests.add(*linked_requests)

    if outcome_obj.outcome_status == OUTCOME_REJECTED:
        remaining_requests = _remaining_active_severe_requests(outcome_obj)

        if remaining_requests.exists():
            hold.supporting_requests.add(*list(remaining_requests))

            remaining_ids = list(
                remaining_requests.values_list("id", flat=True)
            )

            hold.release_note = (
                f"Outcome #{outcome_obj.pk} was rejected, but the temporary "
                f"hold remains active because severe requests {remaining_ids} "
                "are still open."
            )
            hold.save(update_fields=["release_note"])

            logger.info(
                "[Sanctuary] Safety hold retained hold=%s outcome=%s remaining=%s",
                hold.pk,
                outcome_obj.pk,
                remaining_ids,
            )
            return hold

    target = _locked_target(outcome_obj.content_type, outcome_obj.object_id)
    now = timezone.now()

    if outcome_obj.outcome_status == OUTCOME_CONFIRMED:
        hold.status = SanctuarySafetyHold.STATUS_CONFIRMED
        hold.release_note = (
            "Permanent moderation enforcement replaced the temporary hold."
        )
    else:
        restored = False

        if (
            target is not None
            and hold.did_deactivate_target
            and hold.previous_is_active is True
            and hold.previous_is_suspended is False
            and getattr(target, "is_active", False) is False
            and getattr(target, "is_suspended", False) is False
        ):
            restored = (
                target.__class__._default_manager
                .filter(pk=target.pk, is_active=False, is_suspended=False)
                .update(is_active=True)
                > 0
            )

            if restored:
                target.is_active = True

                _schedule_comment_visibility_broadcast(
                    target,
                    visible=True,
                )

        hold.status = SanctuarySafetyHold.STATUS_RELEASED
        hold.release_note = (
            "Temporary hold released after rejected outcome. "
            f"Target restored={restored}."
        )

    hold.ended_at = now
    hold.ended_by = ended_by
    hold.save(
        update_fields=[
            "status",
            "ended_at",
            "ended_by",
            "release_note",
        ]
    )

    logger.info(
        "[Sanctuary] Safety hold closed hold=%s outcome=%s status=%s",
        hold.pk,
        outcome_obj.pk,
        hold.status,
    )

    return hold

def active_safety_hold_for(target) -> SanctuarySafetyHold | None:
    """
    Compatibility wrapper around the canonical hold-access service.

    This preserves parent-aware handling such as:
    PrayerResponse -> Prayer.
    """
    from apps.sanctuary.services.held_content_access import (
        active_safety_hold_for as resolve_active_hold,
    )

    return resolve_active_hold(target)


def is_under_sanctuary_safety_hold(target) -> bool:
    return active_safety_hold_for(target) is not None