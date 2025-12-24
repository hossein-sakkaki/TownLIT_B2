# apps/sanctuary/services/council_actions.py

from __future__ import annotations

import logging
from django.db import transaction
from django.utils import timezone

from apps.sanctuary.models import SanctuaryReview, SanctuaryRequest
from apps.sanctuary.constants.states import PENDING, UNDER_REVIEW, NO_OPINION

logger = logging.getLogger(__name__)


def _model_has_field(model_cls, field_name: str) -> bool:
    try:
        return any(f.name == field_name for f in model_cls._meta.get_fields())
    except Exception:
        return False


HAS_ACTIVE = _model_has_field(SanctuaryReview, "is_active")
HAS_REPLACED_AT = _model_has_field(SanctuaryReview, "replaced_at")


def _open_council_slots_qs(user_id: int):
    """
    Open council slots in open requests where user hasn't voted yet.
    - If is_active exists: only active slots.
    - Else: treat all NO_OPINION slots as open (fallback).
    """
    qs = (
        SanctuaryReview.objects
        .select_related("sanctuary_request")
        .filter(
            reviewer_id=user_id,
            review_status=NO_OPINION,
            sanctuary_request__resolution_mode="council",
            sanctuary_request__status__in=[PENDING, UNDER_REVIEW],
        )
    )
    if HAS_ACTIVE:
        qs = qs.filter(is_active=True)
    return qs


@transaction.atomic
def kick_user_from_open_councils(user_id: int):
    """
    Deactivate user's open council slots so they can't vote.
    Idempotent.
    - If is_active exists: set is_active=False (+ replaced_at if exists)
    - Else: do nothing destructive (fallback) OR optionally delete NO_OPINION slots (NOT recommended)
    """
    now = timezone.now()

    slots = _open_council_slots_qs(user_id).select_for_update()

    count = 0
    for r in slots:
        # defensive under lock
        if r.review_status != NO_OPINION:
            continue

        if HAS_ACTIVE and hasattr(r, "is_active"):
            if r.is_active is False:
                continue
            r.is_active = False
            update_fields = ["is_active"]

            if HAS_REPLACED_AT and hasattr(r, "replaced_at"):
                r.replaced_at = now
                update_fields.append("replaced_at")

            r.save(update_fields=update_fields)
            count += 1
        else:
            # No is_active field => safest is NO-OP (do not delete history)
            # If you want a hard behavior here, tell me and I’ll give a controlled alternative.
            continue

    return count


def replace_user_in_open_councils(*, user_id: int, reason: str, actor_id: int | None = None):
    """
    Remove user slots + replace them with new eligible reviewers.
    Idempotent.
    """
    req_ids = list(
        _open_council_slots_qs(user_id).values_list("sanctuary_request_id", flat=True).distinct()
    )
    if not req_ids:
        return {"affected_requests": 0, "replaced_slots": 0}

    replaced = 0

    # Lazy import to avoid import-time side effects/cycles
    from apps.sanctuary.signals.signals import _replace_reviewer_slot

    for rid in req_ids:
        try:
            req = SanctuaryRequest.objects.only("id", "resolution_mode", "status").get(pk=rid)

            # Optional defensive gate
            if req.status not in (PENDING, UNDER_REVIEW):
                continue
            if req.resolution_mode != "council":
                continue

            _replace_reviewer_slot(req, leaving_user_id=user_id)
            replaced += 1
        except Exception as e:
            logger.warning(
                "[Sanctuary] replace_user_in_open_councils failed req=%s user=%s: %s",
                rid, user_id, e, exc_info=True
            )

    # Belt & suspenders (if is_active exists this will actually deactivate leftovers)
    try:
        kick_user_from_open_councils(user_id)
    except Exception:
        pass

    return {"affected_requests": len(req_ids), "replaced_slots": replaced}
