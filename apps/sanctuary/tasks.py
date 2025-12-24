# apps/sanctuary/tasks.py

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import logging

from apps.sanctuary.models import SanctuaryReview, SanctuaryRequest, SanctuaryOutcome
from apps.sanctuary.constants.states import PENDING, UNDER_REVIEW, NO_OPINION

logger = logging.getLogger(__name__)


# Helpers ---------------------------------------------------------------------------------------
def _has_review_active_field() -> bool:
    """Runtime-safe feature detection (works even if migrations differ across envs)."""
    try:
        return any(f.name == "is_active" for f in SanctuaryReview._meta.get_fields())
    except Exception:
        return False


# Replace inactive council members ---------------------------------------------------------------
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_for_inactive_reviewers(self):
    """
    Canonical 48h replacement.
    Runs frequently (e.g. every 2 hours) but replaces only slots older than 48h.

    Rule:
      - Only NO_OPINION slots are replaceable
      - Only if request is open + in council mode
      - If model has is_active, only active slots are replaceable
      - Replacement calls canonical: _replace_reviewer_slot(req, leaving_user_id)
    """
    try:
        cutoff = timezone.now() - timedelta(hours=48)
        has_active = _has_review_active_field()

        qs = (
            SanctuaryReview.objects
            .select_related("sanctuary_request")
            .filter(
                review_status=NO_OPINION,
                assigned_at__lte=cutoff,
                sanctuary_request__resolution_mode="council",
                sanctuary_request__status__in=[PENDING, UNDER_REVIEW],
            )
            .order_by("assigned_at")
        )

        if has_active:
            qs = qs.filter(is_active=True)

        # Safety batch
        with transaction.atomic():
            locked = (
                qs.select_for_update(skip_locked=True)
                .values_list("id", flat=True)[:300]
            )
        slot_ids = list(locked)

        batch = list(SanctuaryReview.objects.select_related("sanctuary_request").filter(id__in=slot_ids))

        if not batch:
            return {"checked": 0, "replaced_calls": 0}

        # Local import to avoid circular import at module load time
        from apps.sanctuary.signals.signals import _replace_reviewer_slot

        replaced_calls = 0

        for slot in batch:
            req = slot.sanctuary_request

            # Safety checks (defensive)
            if not req:
                continue
            if req.status not in (PENDING, UNDER_REVIEW):
                continue
            if req.resolution_mode != "council":
                continue

            # Re-check slot is still replaceable (avoid double-replace across workers)
            slot_status_now = (
                SanctuaryReview.objects
                .filter(pk=slot.pk)
                .values_list("review_status", flat=True)
                .first()
            )
            if slot_status_now != NO_OPINION:
                continue

            if has_active:
                slot_active_now = (
                    SanctuaryReview.objects
                    .filter(pk=slot.pk)
                    .values_list("is_active", flat=True)
                    .first()
                )
                if not slot_active_now:
                    continue

            try:
                _replace_reviewer_slot(req, slot.reviewer_id)
                replaced_calls += 1
            except Exception as e:
                logger.warning(
                    "[Sanctuary][Task] replace failed req=%s reviewer=%s err=%s",
                    getattr(req, "id", None),
                    getattr(slot, "reviewer_id", None),
                    e,
                    exc_info=True,
                )

        return {"checked": len(batch), "replaced_calls": replaced_calls}

    except Exception as e:
        logger.error("[Sanctuary][Task] check_for_inactive_reviewers crashed: %s", e, exc_info=True)
        raise self.retry(exc=e)


# Reassign inactive admin requests ---------------------------------------------------------------
@shared_task
def check_for_inactive_admins():
    """
    Reassign admin if assigned admin hasn't acted for 24h.

    Notes:
      - We treat "no action" as "admin_assigned_at older than 24h".
      - notify_admins(req) is canonical (handles WS + notifications + council close if needed).
    """
    threshold = timezone.now() - timedelta(hours=24)

    qs = SanctuaryRequest.objects.filter(
        resolution_mode="admin",
        status__in=[PENDING, UNDER_REVIEW],
        admin_assigned_at__isnull=False,
        admin_assigned_at__lt=threshold,
    ).order_by("admin_assigned_at")

    batch = list(qs[:300])
    if not batch:
        return {"checked": 0, "reassigned": 0}

    from apps.sanctuary.signals.signals import notify_admins

    changed = 0
    for req in batch:
        try:
            assigned = notify_admins(req)
            if assigned:
                changed += 1
        except Exception as e:
            logger.warning(
                "[Sanctuary][Task] admin reassign failed req=%s err=%s",
                getattr(req, "id", None),
                e,
                exc_info=True,
            )

    return {"checked": len(batch), "reassigned": changed}


# Reassign inactive appeal admins ---------------------------------------------------------------
@shared_task
def check_for_inactive_appeal_admins():
    """
    Reassign appeal admin if inactive for 24h (appeal pending, not reviewed).
    """
    threshold = timezone.now() - timedelta(hours=24)

    qs = SanctuaryOutcome.objects.filter(
        is_appealed=True,
        admin_reviewed=False,
        admin_assigned_at__isnull=False,
        admin_assigned_at__lt=threshold,
    ).order_by("admin_assigned_at")

    batch = list(qs[:300])
    if not batch:
        return {"checked": 0, "reassigned": 0}

    from apps.sanctuary.signals.signals import assign_admin_for_outcome_appeal

    changed = 0
    for outcome in batch:
        try:
            assigned = assign_admin_for_outcome_appeal(outcome)
            if assigned:
                changed += 1
        except Exception as e:
            logger.warning(
                "[Sanctuary][Task] appeal admin reassign failed outcome=%s err=%s",
                getattr(outcome, "id", None),
                e,
                exc_info=True,
            )

    return {"checked": len(batch), "reassigned": changed}


# Finalize expired appeals ----------------------------------------------------------------------
@shared_task
def check_appeal_deadlines():
    """
    Finalize outcomes whose appeal window expired (no appeal).

    Rule:
      - is_appealed=False
      - appeal_deadline passed
      - finalized_at is null (idempotency)
    """
    now = timezone.now()

    qs = SanctuaryOutcome.objects.filter(
        is_appealed=False,
        appeal_deadline__isnull=False,
        appeal_deadline__lt=now,
        finalized_at__isnull=True,
    ).order_by("appeal_deadline")

    batch = list(qs[:300])
    if not batch:
        return {"checked": 0, "finalized": 0}

    from apps.sanctuary.signals.signals import finalize_sanctuary_outcome

    finalized = 0
    for outcome in batch:
        try:
            finalize_sanctuary_outcome(outcome)
            finalized += 1
        except Exception as e:
            logger.warning(
                "[Sanctuary][Task] finalize deadline failed outcome=%s err=%s",
                getattr(outcome, "id", None),
                e,
                exc_info=True,
            )

    return {"checked": len(batch), "finalized": finalized}
