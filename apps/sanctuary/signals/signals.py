# apps/sanctuary/signals/signals.py

import logging
from datetime import timedelta
from django.db.models import Q, F
from django.db.models.functions import Coalesce

from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone


from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from apps.sanctuary.services.admin_pool import sanctuary_admin_queryset
from apps.notifications.services.services import create_and_dispatch_notification
from apps.sanctuary.services.link_resolver import resolve_sanctuary_target_link

from apps.sanctuary.models import SanctuaryRequest, SanctuaryReview, SanctuaryOutcome, SanctuaryParticipantProfile
from apps.sanctuary.services.council_engine import CouncilSelectionEngine
from apps.sanctuary.realtime.utils import (
    normalize_content_type,
    sanitize_group_part,
)
from apps.sanctuary.services.counter_resolver import (
    resolve_active_report_count,
)
from apps.sanctuary.services.threshold_resolver import (
    resolve_ui_threshold,
)


from apps.sanctuary.constants.states import (
    PENDING,
    UNDER_REVIEW,
    RESOLVED,
    REJECTED,
    NO_OPINION,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
    OUTCOME_CONFIRMED,
    OUTCOME_REJECTED,
)

from apps.sanctuary.services.decision_engine import (
    should_form_council,
    should_admin_fast_track,
)

logger = logging.getLogger(__name__)
User = get_user_model()



# --- Council helpers -------------------------------------------------
def _has_review_active_field() -> bool:
    # Safe runtime feature detection
    return any(f.name == "is_active" for f in SanctuaryReview._meta.get_fields())


def _busy_council_user_ids() -> set[int]:
    """
    Busy = has an ACTIVE council slot in another open request with NO_OPINION.
    Once user votes (not NO_OPINION), they are FREE for new councils.
    """
    qs = SanctuaryReview.objects.filter(
        sanctuary_request__resolution_mode="council",
        sanctuary_request__status__in=[PENDING, UNDER_REVIEW],
        review_status=NO_OPINION,
    )
    if _has_review_active_field():
        qs = qs.filter(is_active=True)

    return set(qs.values_list("reviewer_id", flat=True))

# --- General helpers -------------------------------------------------
def _model_has_field(model_cls, field_name: str) -> bool:
    try:
        return any(f.name == field_name for f in model_cls._meta.get_fields())
    except Exception:
        return False


def _is_denom_match(user, branch: str | None, family: str | None) -> bool:
    """Return True if user's member_profile matches target denom (branch or family)."""
    mp = getattr(user, "member_profile", None)
    if not mp:
        return False
    if branch and getattr(mp, "denomination_branch", None) == branch:
        return True
    if family and getattr(mp, "denomination_family", None) == family:
        return True
    return False


# ---------------------------------------------------------------------
# WS helper: broadcast to sanctuary request group
# ---------------------------------------------------------------------
def _ws_broadcast_request(request_id: int, event: str, data: dict):
    """Send WS event to 'sanctuary.request.{id}' group."""
    try:
        layer = get_channel_layer()
        if not layer:
            return
        async_to_sync(layer.group_send)(
            f"sanctuary.request.{request_id}",
            {
                "type": "dispatch_event",
                "app": "sanctuary",
                "event": event,
                "data": data,
            },
        )
    except Exception as e:
        logger.warning("[Sanctuary][WS] broadcast failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------
# WS helper: broadcast to sanctuary TARGET group (counter sync)
# ---------------------------------------------------------------------

def _ws_broadcast_target(
    *,
    request_type: str,
    content_type,
    object_id: int,
    count: int,
    threshold: int,
):
    """
    Broadcast sanctuary counter update to a SAFE Channels group.

    Group format:
      sanctuary.target.{request_type}.{app_label.model}.{object_id}
    """

    try:
        layer = get_channel_layer()
        if not layer:
            return

        # ----------------------------------------
        # Normalize + sanitize group name parts
        # ----------------------------------------
        rt = sanitize_group_part(request_type)

        # content_type may be string OR ContentType object
        normalized_ct = normalize_content_type(content_type)
        ct = sanitize_group_part(normalized_ct)

        oid = int(object_id)

        group = f"sanctuary.target.{rt}.{ct}.{oid}"

        # ----------------------------------------
        # Send unified WS event
        # ----------------------------------------
        async_to_sync(layer.group_send)(
            "sanctuary_global",
            {
                "type": "dispatch_event",
                "app": "sanctuary",
                "event": "counter_updated",
                "data": {
                    "request_type": request_type,
                    "content_type": normalized_ct,
                    "object_id": oid,
                    "count": int(count),
                    "threshold": int(threshold),
                },
            },
        )


    except Exception as e:
        logger.warning(
            "[Sanctuary][WS] broadcast target counter failed: %s",
            e,
            exc_info=True,
        )


# ---------------------------------------------------------------------
# Safe target mutations
# ---------------------------------------------------------------------
def _inc_reports_count(target_obj) -> int:
    """
    Atomic increment: prevents lost updates under concurrency.
    Returns the NEW reports_count.
    """
    if not target_obj:
        return 0

    # must have pk and field
    if not hasattr(target_obj, "pk") or not target_obj.pk:
        return 0
    if not hasattr(target_obj, "reports_count"):
        return 0

    try:
        Model = target_obj.__class__

        # ✅ Atomic DB-side increment (handles NULL safely via Coalesce)
        Model.objects.filter(pk=target_obj.pk).update(
            reports_count=Coalesce(F("reports_count"), 0) + 1
        )

        # Read back the new value (portable across DBs)
        new_val = Model.objects.filter(pk=target_obj.pk).values_list("reports_count", flat=True).first()
        return int(new_val or 0)

    except Exception as e:
        logger.warning("[Sanctuary] inc reports_count failed: %s", e, exc_info=True)
        return 0


def _set_suspended(target_obj, suspended: bool):
    """Set is_suspended if exists."""
    if not target_obj or not hasattr(target_obj, "is_suspended"):
        return
    try:
        setattr(target_obj, "is_suspended", bool(suspended))
        target_obj.save(update_fields=["is_suspended"])
    except Exception as e:
        logger.warning("[Sanctuary] set is_suspended failed: %s", e, exc_info=True)


def _set_active(target_obj, active: bool):
    """Set is_active if exists."""
    if not target_obj or not hasattr(target_obj, "is_active"):
        return
    try:
        setattr(target_obj, "is_active", bool(active))
        target_obj.save(update_fields=["is_active"])
    except Exception as e:
        logger.warning("[Sanctuary] set is_active failed: %s", e, exc_info=True)


def _reset_reports_count(target_obj):
    """Reset reports_count if exists."""
    if not target_obj or not hasattr(target_obj, "reports_count"):
        return
    try:
        setattr(target_obj, "reports_count", 0)
        target_obj.save(update_fields=["reports_count"])
    except Exception as e:
        logger.warning("[Sanctuary] reset reports_count failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------
# Council slots
# ---------------------------------------------------------------------
def _deactivate_open_council_slots(req: SanctuaryRequest) -> int:
    try:
        qs = SanctuaryReview.objects.filter(
            sanctuary_request=req,
            review_status=NO_OPINION,
        )

        if hasattr(SanctuaryReview, "is_active"):
            qs = qs.filter(is_active=True)

            update_kwargs = {"is_active": False}

            # Optional audit field
            if _model_has_field(SanctuaryReview, "replaced_at"):
                update_kwargs["replaced_at"] = timezone.now()

            return qs.update(**update_kwargs)

        return 0

    except Exception as e:
        logger.warning("[Sanctuary] deactivate council slots failed: %s", e, exc_info=True)
        return 0


# ---------------------------------------------------------------------
# Council replacement
# ---------------------------------------------------------------------
def _replace_reviewer_slot(req: SanctuaryRequest, leaving_user_id: int):
    """
    Replace a council member slot with a new eligible CustomUser.
    - Keep language match
    - Keep >=8 denom matches across 12 slots
    - Exclude busy users (NO_OPINION in other active council requests)
    """
    try:
        engine = CouncilSelectionEngine(request_obj=req)
        owner = engine.resolve_target_owner()
        if not owner:
            logger.warning("[Sanctuary] replace_reviewer_slot: cannot resolve target owner for req=%s", req.id)
            return

        target_langs = engine.resolve_target_languages(owner)
        branch, family = engine.resolve_target_denom(owner)

        has_active_field = _model_has_field(SanctuaryReview, "is_active")
        has_trad_field = _model_has_field(SanctuaryReview, "is_primary_tradition_match")

        # Current reviewer ids (prefer active slots if field exists)
        reviews_qs = req.reviews.all()
        
        if has_active_field:
            reviews_qs = reviews_qs.filter(is_active=True)

        current_ids = list(reviews_qs.values_list("reviewer_id", flat=True))
        if leaving_user_id not in current_ids:
            return  # already replaced (idempotent)

        remaining_ids = [i for i in current_ids if i != leaving_user_id]

        # Count denom matches among remaining slots
        cond = Q()
        if branch:
            cond |= Q(member_profile__denomination_branch=branch)
        if family:
            cond |= Q(member_profile__denomination_family=family)

        denom_count = 0
        if cond and remaining_ids:
            denom_count = User.objects.filter(id__in=remaining_ids).filter(cond).count()

        # Base eligible pool: verified + participant + language + not busy + not requester/admin
        base = engine.base_queryset(target_langs)

        # Exclude everyone already in this request (incl leaving)
        base = base.exclude(id__in=current_ids)

        # If denom_count dropped below 8 -> replacement MUST be denom-match
        if denom_count < 8:
            base = engine.denom_match_queryset(base, branch, family)

        new_user = base.order_by("?").first()
        if not new_user:
            assigned = notify_admins(req)
            _ws_broadcast_request(
                req.id,
                "council_pool_exhausted_admin_fallback",
                {"assigned_admin_id": getattr(assigned, "id", None)},
            )
            return

        # Swap slot atomically
        with transaction.atomic():
            req_locked = SanctuaryRequest.objects.select_for_update().get(pk=req.pk)

            leaving_qs = SanctuaryReview.objects.select_for_update().filter(
                sanctuary_request=req_locked,
                reviewer_id=leaving_user_id,
            )
            if has_active_field:
                leaving_qs = leaving_qs.filter(is_active=True)

            leaving_review = leaving_qs.first()
            if not leaving_review:
                return

            # Only replace if still NO_OPINION
            if leaving_review.review_status != NO_OPINION:
                return

            # Deactivate or delete leaving slot
            if has_active_field and hasattr(leaving_review, "is_active"):
                leaving_review.is_active = False

                update_fields = ["is_active"]

                # Optional audit field
                if _model_has_field(SanctuaryReview, "replaced_at") and hasattr(leaving_review, "replaced_at"):
                    leaving_review.replaced_at = timezone.now()
                    update_fields.append("replaced_at")

                leaving_review.save(update_fields=update_fields)
            else:
                leaving_review.delete()

            # Create (or revive) new slot
            now = timezone.now()
            defaults = {"review_status": NO_OPINION, "assigned_at": now}
            if has_active_field:
                defaults["is_active"] = True
            if has_trad_field:
                defaults["is_primary_tradition_match"] = _is_denom_match(new_user, branch, family)

            review, created = SanctuaryReview.objects.get_or_create(
                sanctuary_request=req_locked,
                reviewer=new_user,
                defaults=defaults,
            )

            # If exists but inactive, revive it (no spam)
            if (not created) and has_active_field and hasattr(review, "is_active") and review.is_active is False:
                review.is_active = True
                review.review_status = NO_OPINION
                review.assigned_at = now
                update_fields = ["is_active", "review_status", "assigned_at"]
                if has_trad_field and hasattr(review, "is_primary_tradition_match"):
                    review.is_primary_tradition_match = _is_denom_match(new_user, branch, family)
                    update_fields.append("is_primary_tradition_match")
                review.save(update_fields=update_fields)
                created = True

        # ✅ Notify new reviewer ONLY if created/revived
        if created:
            create_and_dispatch_notification(
                recipient=new_user,
                actor=req.requester,
                notif_type="sanctuary_member_review_request",
                message=f"You have been selected to review a Sanctuary request.",
                target_obj=req,
                action_obj=review,
                link=resolve_sanctuary_target_link(req),
                dedupe=True,
                extra_payload={"request_id": req.id, "review_id": review.id},
            )

        # WS update (always useful if replacement succeeded)
        _ws_broadcast_request(
            req.id,
            "reviewer_replaced",
            {
                "request_id": req.id,
                "old_reviewer_id": leaving_user_id,
                "new_reviewer_id": new_user.id,
                "new_reviewer_username": new_user.username,
            },
        )

    except Exception as e:
        logger.warning("[Sanctuary] _replace_reviewer_slot failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------
# Admin assignment + Notification
# ---------------------------------------------------------------------
def notify_admins(sanctuary_request: SanctuaryRequest, *, force: bool = False, stale_after_hours: int = 24):
    """
    Assign/reassign a Sanctuary admin (idempotent + race-safe).

    - If an admin is already assigned and NOT stale -> no-op (returns current admin).
    - If stale (or no admin) -> assigns a new admin from sanctuary_admin_queryset().
    - If switching from council -> admin, deactivates open NO_OPINION council slots.
    - Uses row lock to prevent concurrent reassigns by multiple Celery workers.
    """
    try:
        from apps.sanctuary.services.admin_pool import sanctuary_admin_queryset

        now = timezone.now()
        stale_cutoff = now - timedelta(hours=int(stale_after_hours))

        with transaction.atomic():
            # Lock the request row to avoid concurrent reassigns
            req = (
                SanctuaryRequest.objects
                .select_for_update()
                .select_related("assigned_admin", "requester")
                .get(pk=sanctuary_request.pk)
            )

            # If request is not open, do nothing
            if req.status not in (PENDING, UNDER_REVIEW):
                return req.assigned_admin

            old_admin_id = req.assigned_admin_id
            old_assigned_at = getattr(req, "admin_assigned_at", None)

            # Idempotent guard: keep existing admin if not stale and not forced
            if old_admin_id and not force:
                if old_assigned_at and old_assigned_at >= stale_cutoff:
                    return req.assigned_admin

            # Build admin pool
            admins = sanctuary_admin_queryset()

            # Prefer changing admin; exclude current one if exists
            if old_admin_id:
                admins = admins.exclude(id=old_admin_id)

            new_admin = admins.order_by("?").first()

            # If no replacement found, keep old admin if present
            if not new_admin:
                if old_admin_id:
                    # Ensure mode/status are consistent (best-effort)
                    if req.resolution_mode != "admin":
                        req.resolution_mode = "admin"
                        req.status = UNDER_REVIEW
                        req.save(update_fields=["resolution_mode", "status"])
                    return req.assigned_admin

                logger.warning("[Sanctuary] No admin found for request %s", req.id)
                return None

            was_council = (req.resolution_mode == "council")
            changed_admin = (old_admin_id != new_admin.id)
            mode_changed = (req.resolution_mode != "admin")

            # Assign admin + move request to admin flow
            req.assigned_admin = new_admin
            req.admin_assigned_at = now
            req.status = UNDER_REVIEW
            req.resolution_mode = "admin"
            req.save(update_fields=["assigned_admin", "admin_assigned_at", "status", "resolution_mode"])

            # Close any open council slots if we came from council OR if there are lingering NO_OPINION slots
            closed_slots = 0
            if was_council or req.reviews.filter(review_status=NO_OPINION).exists():
                closed_slots = _deactivate_open_council_slots(req)

        # ---- Outside transaction: send WS + notifications only when meaningful change happened ----

        if closed_slots:
            _ws_broadcast_request(
                req.id,
                "council_closed",
                {
                    "request_id": req.id,
                    "closed_slots": closed_slots,
                    "reason": "fallback_to_admin",
                },
            )

        # Notify only if admin actually changed OR mode changed into admin (avoid spam)
        if changed_admin or mode_changed:
            create_and_dispatch_notification(
                recipient=new_admin,
                actor=req.requester,
                notif_type="sanctuary_admin_assignment",
                message=f"You have been assigned to review a Sanctuary request.",
                target_obj=req,
                action_obj=None,
                link=resolve_sanctuary_target_link(req),
                dedupe=True,
                extra_payload={
                    "request_id": req.id,
                    "request_type": req.request_type,
                    "closed_council_slots": closed_slots,
                    "reassigned": bool(old_admin_id),
                },
            )

            _ws_broadcast_request(
                req.id,
                "admin_assigned",
                {
                    "request_id": req.id,
                    "assigned_admin_id": new_admin.id,
                    "assigned_admin_username": getattr(new_admin, "username", ""),
                    "reassigned": bool(old_admin_id),
                },
            )

        return new_admin

    except Exception as e:
        logger.warning("[Sanctuary] notify_admins failed: %s", e, exc_info=True)
        return None

# ---------------------------------------------------------------------
# Council distribution (12 verified participants)
# ---------------------------------------------------------------------
def distribute_to_verified_members(sanctuary_request: SanctuaryRequest, count: int = 12):
    try:
        engine = CouncilSelectionEngine(request_obj=sanctuary_request)
        selected_users = engine.select_council(total=count, denom_majority=8)

        if not selected_users:
            assigned = notify_admins(sanctuary_request)
            _ws_broadcast_request(
                sanctuary_request.id,
                "council_unavailable_admin_fallback",
                {"assigned_admin_id": getattr(assigned, "id", None)},
            )
            return None

        # ✅ Lock request to avoid double formation
        with transaction.atomic():
            req = SanctuaryRequest.objects.select_for_update().get(pk=sanctuary_request.pk)

            # If request already moved to admin flow, don't form council
            if req.resolution_mode == "admin" or req.assigned_admin_id:
                return None

            # If council already formed (active slots exist), no-op
            reviews_qs = req.reviews.all()
            if hasattr(SanctuaryReview, "is_active"):
                reviews_qs = reviews_qs.filter(is_active=True)

            if reviews_qs.exists():
                return None

            owner = engine.resolve_target_owner()
            branch, family = engine.resolve_target_denom(owner) if owner else (None, None)

            now = timezone.now()
            has_trad_field = _model_has_field(SanctuaryReview, "is_primary_tradition_match")
            has_active_field = _model_has_field(SanctuaryReview, "is_active")

            for u in selected_users:
                defaults = {"review_status": NO_OPINION, "assigned_at": now}
                if has_active_field:
                    defaults["is_active"] = True
                if has_trad_field:
                    defaults["is_primary_tradition_match"] = _is_denom_match(u, branch, family)

                review, created = SanctuaryReview.objects.get_or_create(
                    sanctuary_request=req,
                    reviewer=u,
                    defaults=defaults,
                )

                # revive inactive
                if (not created) and has_active_field and hasattr(review, "is_active") and review.is_active is False:
                    review.is_active = True
                    review.review_status = NO_OPINION
                    review.assigned_at = now
                    update_fields = ["is_active", "review_status", "assigned_at"]
                    if has_trad_field and hasattr(review, "is_primary_tradition_match"):
                        review.is_primary_tradition_match = _is_denom_match(u, branch, family)
                        update_fields.append("is_primary_tradition_match")
                    review.save(update_fields=update_fields)
                    created = True

                if created:
                    create_and_dispatch_notification(
                        recipient=u,
                        actor=req.requester,
                        notif_type="sanctuary_member_review_request",
                        message=f"A Sanctuary request requires your review.",
                        target_obj=req,
                        action_obj=review,
                        link=resolve_sanctuary_target_link(req),
                        dedupe=True,
                        extra_payload={"request_id": req.id, "review_id": review.id},
                    )

            req.status = UNDER_REVIEW
            req.resolution_mode = "council"
            req.save(update_fields=["status", "resolution_mode"])

        _ws_broadcast_request(
            sanctuary_request.id,
            "council_formed",
            {"member_count": len(selected_users), "expires_in_hours": 48},
        )
        return selected_users

    except Exception as e:
        logger.warning("[Sanctuary] distribute_to_verified_members failed: %s", e, exc_info=True)
        return None


# ---------------------------------------------------------------------
# Outcome finalization
# ---------------------------------------------------------------------
def finalize_sanctuary_outcome(outcome: SanctuaryOutcome):
    """
    Apply outcome to target + notify parties.
    IMPORTANT: Do NOT touch admin_reviewed here (appeal flow).

    Race-safe + avoids "finalized without work":
      1) Validate requirements
      2) Atomically claim finalized_at (idempotency)
      3) Apply effects + notify
    """
    try:
        # Always work with fresh data
        outcome = SanctuaryOutcome.objects.get(pk=outcome.pk)

        # ✅ Validate first (avoid finalized without doing anything)
        if outcome.outcome_status not in (OUTCOME_CONFIRMED, OUTCOME_REJECTED):
            return

        qs = outcome.sanctuary_requests.all()
        if not qs.exists():
            return

        # ✅ Atomic idempotency guard AFTER validation
        claimed = (
            SanctuaryOutcome.objects
            .filter(pk=outcome.pk, finalized_at__isnull=True)
            .update(finalized_at=timezone.now())
        )
        if claimed == 0:
            return  # already finalized elsewhere

        # refresh if you want (optional)
        outcome.refresh_from_db()

        req0 = qs.order_by("id").first()
        target = getattr(req0, "content_object", None)

        # Apply effects (best-effort)
        if outcome.outcome_status == OUTCOME_CONFIRMED:
            _set_active(target, False)
            _set_suspended(target, True)
            _reset_reports_count(target)
            new_req_status = RESOLVED
        else:  # OUTCOME_REJECTED
            _set_suspended(target, False)
            _reset_reports_count(target)
            new_req_status = REJECTED

        # Mark linked requests completed
        for r in qs:
            try:
                r.status = new_req_status
                r.save(update_fields=["status"])
            except Exception:
                pass

        # Notify requester
        create_and_dispatch_notification(
            recipient=req0.requester,
            actor=None,
            notif_type="sanctuary_outcome_finalized",
            message=f"Sanctuary outcome finalized: {outcome.outcome_status}.",
            target_obj=outcome,
            action_obj=req0,
            link=resolve_sanctuary_target_link(req0), 
            dedupe=False,
            extra_payload={"outcome_id": outcome.id, "status": outcome.outcome_status},
        )

        # Notify reported user (if different)
        if isinstance(target, User) and target.id != req0.requester_id:
            create_and_dispatch_notification(
                recipient=target,
                actor=None,
                notif_type="sanctuary_outcome_finalized",
                message=f"A Sanctuary case involving you has been finalized: {outcome.outcome_status}.",
                target_obj=outcome,
                action_obj=req0,
                link=resolve_sanctuary_target_link(req0), 
                dedupe=False,
                extra_payload={"outcome_id": outcome.id, "status": outcome.outcome_status},
            )

        # Notify council participants
        participant_ids = list(req0.reviews.values_list("reviewer_id", flat=True).distinct())
        if participant_ids:
            for u in User.objects.filter(id__in=participant_ids):
                create_and_dispatch_notification(
                    recipient=u,
                    actor=None,
                    notif_type="sanctuary_outcome_finalized",
                    message=f"Sanctuary outcome finalized: {outcome.outcome_status}.",
                    target_obj=outcome,
                    action_obj=req0,
                    link=resolve_sanctuary_target_link(req0), 
                    dedupe=False,
                    extra_payload={"outcome_id": outcome.id, "status": outcome.outcome_status},
                )

        # WS update
        _ws_broadcast_request(
            req0.id,
            "outcome_finalized",
            {"outcome_id": outcome.id, "status": outcome.outcome_status},
        )

    except Exception as e:
        logger.warning("[Sanctuary] finalize_sanctuary_outcome failed: %s", e, exc_info=True)


# ---------------------------------------------------------------------
# 1) Request created → snapshot + routing
# ---------------------------------------------------------------------
@receiver(post_save, sender=SanctuaryRequest, dispatch_uid="sanctuary.request.created.v3")
def on_sanctuary_request_created(sender, instance: SanctuaryRequest, created: bool, **kwargs):
    if not created:
        return

    def _after_commit():
        try:
            target = getattr(instance, "content_object", None)

            # Historical analytics only
            _inc_reports_count(target)

            # 🔥 Active wave counter (UI source of truth)
            active_count = resolve_active_report_count(
                request_type=instance.request_type,
                content_type=instance.content_type,
                object_id=instance.object_id,
            )

            instance.report_count_snapshot = active_count
            instance.save(update_fields=["report_count_snapshot"])

            # 🔥 UI threshold (NOT admin fast-track)
            ui_threshold = resolve_ui_threshold(instance.request_type)

            _ws_broadcast_target(
                request_type=instance.request_type,
                content_type=instance.content_type,
                object_id=instance.object_id,
                count=active_count,
                threshold=ui_threshold,
            )

            # Routing logic (separate concern)
            if should_admin_fast_track(instance.request_type, active_count):
                notify_admins(instance)
            elif should_form_council(instance.request_type, active_count):
                distribute_to_verified_members(instance)

        except Exception as e:
            logger.warning(
                "[Sanctuary] on_request_created failed: %s",
                e,
                exc_info=True,
            )

    transaction.on_commit(_after_commit)


# ---------------------------------------------------------------------
# 2) Review saved → broadcast + outcome check
# ---------------------------------------------------------------------
@receiver(post_save, sender=SanctuaryReview, dispatch_uid="sanctuary.review.saved.v1")
def on_review_saved(sender, instance: SanctuaryReview, created: bool, **kwargs):
    # IMPORTANT: avoid side effects inside atomic
    def _after_commit():

        # Skip deactivated slots (replacement flow), avoid noisy "review_updated"
        if hasattr(instance, "is_active") and instance.is_active is False:
            return

        try:
            req = instance.sanctuary_request

            _ws_broadcast_request(
                req.id,
                "review_updated",
                {
                    "review_id": instance.id,
                    "review_status": instance.review_status,
                    "reviewer_id": instance.reviewer_id,
                    "reviewer_username": getattr(instance.reviewer, "username", ""),
                    "reviewed_at": instance.reviewed_at.isoformat() if instance.reviewed_at else None,
                },
            )

            # Only check completion for council flow
            if instance.review_status in (VIOLATION_CONFIRMED, VIOLATION_REJECTED):
                if req.resolution_mode == "council":
                    _check_council_completion_and_finalize(req)

        except Exception as e:
            logger.warning("[Sanctuary] on_review_saved failed: %s", e, exc_info=True)

    transaction.on_commit(_after_commit)


def _check_council_completion_and_finalize(req: SanctuaryRequest):
    """
    Council rule:
      - early win at 7 votes
      - never create multiple outcomes for same request
    """
    try:
        # ✅ Guard: only council flow can finalize by votes
        if req.resolution_mode != "council":
            return

        # Idempotency
        if req.outcomes.filter(outcome_status__in=[OUTCOME_CONFIRMED, OUTCOME_REJECTED]).exists():
            return

        reviews = req.reviews.exclude(review_status=NO_OPINION)
        confirm = reviews.filter(review_status=VIOLATION_CONFIRMED).count()
        reject = reviews.filter(review_status=VIOLATION_REJECTED).count()

        if confirm < 7 and reject < 7:
            return

        decided_status = OUTCOME_CONFIRMED if confirm >= 7 else OUTCOME_REJECTED

        with transaction.atomic():
            req_locked = SanctuaryRequest.objects.select_for_update().get(pk=req.pk)

            if req_locked.resolution_mode != "council":
                return

            if req_locked.outcomes.filter(outcome_status__in=[OUTCOME_CONFIRMED, OUTCOME_REJECTED]).exists():
                return

            outcome = SanctuaryOutcome.objects.create(
                outcome_status=decided_status,
                content_type=req_locked.content_type,
                object_id=req_locked.object_id,
                appeal_deadline=timezone.now() + timedelta(days=7),
            )
            outcome.sanctuary_requests.add(req_locked)

            # ✅ Close remaining open slots to prevent late votes / replacement noise
            _deactivate_open_council_slots(req_locked)

        finalize_sanctuary_outcome(outcome)

    except Exception as e:
        logger.warning("[Sanctuary] council finalize failed: %s", e, exc_info=True)



# ---------------------------------------------------------------------
# 3) Outcome saved → appeal assignment (admin)
# ---------------------------------------------------------------------
@receiver(post_save, sender=SanctuaryOutcome, dispatch_uid="sanctuary.outcome.saved.v1")
def on_outcome_saved(sender, instance: SanctuaryOutcome, created: bool, **kwargs):
    def _after_commit():
        try:
            if instance.is_appealed and not instance.assigned_admin_id and not instance.admin_reviewed:
                _assign_admin_for_outcome_appeal(instance)
        except Exception as e:
            logger.warning("[Sanctuary] on_outcome_saved failed: %s", e, exc_info=True)

    transaction.on_commit(_after_commit)


def _assign_admin_for_outcome_appeal(outcome: SanctuaryOutcome):
    """Assign random staff for appeal review + notify."""
    try:
        admins = sanctuary_admin_queryset()

        if outcome.assigned_admin_id:
            admins = admins.exclude(id=outcome.assigned_admin_id)

        assigned = admins.order_by("?").first()
        if not assigned:
            logger.warning("[Sanctuary] No admin found for outcome appeal %s", outcome.id)
            return None

        outcome.assigned_admin = assigned
        outcome.admin_assigned_at = timezone.now()
        outcome.save(update_fields=["assigned_admin", "admin_assigned_at"])

        create_and_dispatch_notification(
            recipient=assigned,
            actor=None,
            notif_type="sanctuary_appeal_assignment",
            message=f"You have been assigned to review a Sanctuary appeal.",
            target_obj=outcome,
            action_obj=None,
            link=f"/sanctuary/outcome/{outcome.id}/appeal/",
            dedupe=True,
            extra_payload={"outcome_id": outcome.id},
        )

        return assigned

    except Exception as e:
        logger.warning("[Sanctuary] appeal admin assign failed: %s", e, exc_info=True)
        return None


def assign_admin_for_outcome_appeal(outcome: SanctuaryOutcome):
    """Public wrapper."""
    return _assign_admin_for_outcome_appeal(outcome)


# ---------------------------------------------------------------------
# participant profile safety net
# ---------------------------------------------------------------------
@receiver(pre_save, sender=SanctuaryParticipantProfile, dispatch_uid="sanctuary.participantprofile.presave.v2")
def participantprofile_presave(sender, instance: SanctuaryParticipantProfile, **kwargs):
    """
    Store old eligibility + enforce invariants:
      - If is_eligible becomes False => must not remain participant.
    """
    if not instance.pk:
        instance._old_is_eligible = True  # default assumption for new rows
        return

    old = (
        SanctuaryParticipantProfile.objects
        .filter(pk=instance.pk)
        .only("is_eligible", "is_participant", "participant_opted_out_at")
        .first()
    )
    instance._old_is_eligible = getattr(old, "is_eligible", True)

    # ✅ Safety invariant: not eligible => cannot be participant
    if instance.is_eligible is False and getattr(instance, "is_participant", False):
        now = timezone.now()
        instance.is_participant = False
        if not getattr(instance, "participant_opted_out_at", None):
            instance.participant_opted_out_at = now
        # NOTE: do not touch opted_in_at here (audit)


@receiver(post_save, sender=SanctuaryParticipantProfile, dispatch_uid="sanctuary.participantprofile.postsave.v2")
def participantprofile_postsave(sender, instance: SanctuaryParticipantProfile, created: bool, **kwargs):
    """
    Safety net: if eligibility flips True -> False outside the service,
    remove user from any open councils (and optionally replace immediately).
    """
    if created:
        return

    try:
        if getattr(instance, "_skip_council_actions", False):
            return

        old_val = getattr(instance, "_old_is_eligible", True)
        if old_val is True and instance.is_eligible is False:
            user_id = instance.user_id
            reason = (getattr(instance, "eligible_reason", None) or "").strip() or "blocked"
            actor_id = getattr(instance, "eligible_changed_by_id", None)

            def _after_commit():
                # Option A (recommended): replace immediately (you said optional hook)
                try:
                    from apps.sanctuary.services.council_actions import replace_user_in_open_councils
                    replace_user_in_open_councils(user_id=user_id, reason=reason, actor_id=actor_id)
                    return
                except Exception:
                    pass

                # Option B (fallback): just kick (no replacement)
                try:
                    from apps.sanctuary.services.council_actions import kick_user_from_open_councils
                    kick_user_from_open_councils(user_id)
                except Exception as e:
                    logger.warning("[Sanctuary] kick/replace failed user=%s: %s", user_id, e, exc_info=True)

            transaction.on_commit(_after_commit)

    except Exception as e:
        logger.warning("[Sanctuary] participantprofile_postsave safety net failed: %s", e, exc_info=True)
