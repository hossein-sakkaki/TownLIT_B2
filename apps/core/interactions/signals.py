# apps/core/interactions/signals.py

import logging
from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from apps.posts.models.comment import Comment
from apps.posts.models.reaction import Reaction

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# Helpers (defensive + generic)
# ------------------------------------------------------------
def _has_field(obj, field: str) -> bool:
    return hasattr(obj, field)


def _supports_comment_counters(target) -> bool:
    return (
        target
        and _has_field(target, "comments_count")
        and _has_field(target, "recomments_count")
    )


def _supports_reaction_counters(target) -> bool:
    return (
        target
        and _has_field(target, "reactions_count")
        and _has_field(target, "reactions_breakdown")
    )


def _safe_inc(model_cls, pk, field: str, by: int = 1):
    # Atomic DB-side increment
    model_cls.objects.filter(pk=pk).update(**{field: F(field) + int(by)})


def _safe_dec_non_negative(model_cls, pk, field: str, by: int = 1):
    """
    Best-effort clamp:
    - In MySQL, negative is unlikely but possible if data corrupted or double events happen.
    - We do atomic decrement first, then clamp in a second query.
    """
    model_cls.objects.filter(pk=pk).update(**{field: F(field) - int(by)})
    # clamp (portable)
    model_cls.objects.filter(pk=pk, **{f"{field}__lt": 0}).update(**{field: 0})


def _update_reaction_breakdown_locked(target_model, target_pk, reaction_type: str, delta: int):
    """
    Race-safe JSON update:
    - lock the row
    - update breakdown dict
    - save
    """
    if not reaction_type:
        return

    with transaction.atomic():
        obj = target_model.objects.select_for_update().filter(pk=target_pk).first()
        if not obj:
            return

        breakdown = dict(getattr(obj, "reactions_breakdown", {}) or {})
        new_val = int(breakdown.get(reaction_type, 0)) + int(delta)

        if new_val <= 0:
            breakdown.pop(reaction_type, None)
        else:
            breakdown[reaction_type] = new_val

        obj.reactions_breakdown = breakdown
        obj.save(update_fields=["reactions_breakdown"])


# ============================================================
# COMMENTS
# ============================================================

@receiver(pre_save, sender=Comment, dispatch_uid="interactions.comment.presave.track_active")
def comment_presave_track_active(sender, instance: Comment, **kwargs):
    """
    Track is_active transitions (soft delete / restore).
    Store previous state on instance.
    """
    if not instance.pk:
        instance._old_is_active = None
        instance._old_recomment_id = None
        return

    old = Comment.objects.filter(pk=instance.pk).only("is_active", "recomment_id").first()
    instance._old_is_active = getattr(old, "is_active", None)
    instance._old_recomment_id = getattr(old, "recomment_id", None)


@receiver(post_save, sender=Comment, dispatch_uid="interactions.comment.postsave.counters")
def comment_postsave_counters(sender, instance: Comment, created: bool, **kwargs):
    """
    Handles:
    - create active comment  -> +1
    - soft delete (True -> False) -> -1
    - restore (False -> True) -> +1
    NOTE: if recomment_id changes (rare), you can extend later.
    """
    target = getattr(instance, "content_object", None)
    if not _supports_comment_counters(target):
        return

    model_cls = target.__class__
    pk = target.pk

    # New row
    if created:
        if instance.is_active:
            if instance.recomment_id:
                _safe_inc(model_cls, pk, "recomments_count", 1)
            else:
                _safe_inc(model_cls, pk, "comments_count", 1)
        return

    # Existing row: check active toggle
    old_is_active = getattr(instance, "_old_is_active", None)
    if old_is_active is None:
        return  # safety

    if old_is_active is True and instance.is_active is False:
        # soft delete
        if instance.recomment_id:
            _safe_dec_non_negative(model_cls, pk, "recomments_count", 1)
        else:
            _safe_dec_non_negative(model_cls, pk, "comments_count", 1)

    elif old_is_active is False and instance.is_active is True:
        # restore
        if instance.recomment_id:
            _safe_inc(model_cls, pk, "recomments_count", 1)
        else:
            _safe_inc(model_cls, pk, "comments_count", 1)


@receiver(post_delete, sender=Comment, dispatch_uid="interactions.comment.postdelete.counters")
def comment_postdelete_counters(sender, instance: Comment, **kwargs):
    """
    Hard delete fallback:
    - If you ever delete rows physically, counters should reflect it.
    - If row was already inactive, we do nothing.
    """
    if not instance.is_active:
        return

    target = getattr(instance, "content_object", None)
    if not _supports_comment_counters(target):
        return

    model_cls = target.__class__
    pk = target.pk

    if instance.recomment_id:
        _safe_dec_non_negative(model_cls, pk, "recomments_count", 1)
    else:
        _safe_dec_non_negative(model_cls, pk, "comments_count", 1)


# ============================================================
# REACTIONS
# ============================================================

@receiver(post_save, sender=Reaction, dispatch_uid="interactions.reaction.postsave.counters")
def reaction_postsave_counters(sender, instance: Reaction, created: bool, **kwargs):
    """
    Only counts on creation.
    If later you allow changing reaction_type, add a pre_save tracker like Comment.
    """
    if not created:
        return

    target = getattr(instance, "content_object", None)
    if not _supports_reaction_counters(target):
        return

    model_cls = target.__class__
    pk = target.pk

    # total (atomic)
    _safe_inc(model_cls, pk, "reactions_count", 1)

    # per-type (locked JSON update)
    _update_reaction_breakdown_locked(model_cls, pk, instance.reaction_type, +1)


@receiver(post_delete, sender=Reaction, dispatch_uid="interactions.reaction.postdelete.counters")
def reaction_postdelete_counters(sender, instance: Reaction, **kwargs):
    target = getattr(instance, "content_object", None)
    if not _supports_reaction_counters(target):
        return

    model_cls = target.__class__
    pk = target.pk

    _safe_dec_non_negative(model_cls, pk, "reactions_count", 1)
    _update_reaction_breakdown_locked(model_cls, pk, instance.reaction_type, -1)
