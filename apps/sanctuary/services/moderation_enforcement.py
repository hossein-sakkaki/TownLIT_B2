# apps/sanctuary/services/moderation_enforcement.py

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

SANCTUARY_CONFIRMED_REASON = "sanctuary_outcome_confirmed"


def _model_field_names(target) -> set[str]:
    try:
        return {field.name for field in target._meta.get_fields()}
    except Exception:
        return set()


@transaction.atomic
def enforce_confirmed_sanctuary_outcome(target, *, reason: str = SANCTUARY_CONFIRMED_REASON) -> bool:
    """
    Apply final moderation after a confirmed Sanctuary outcome.

    Supported fields are detected dynamically so the service remains safe
    for account, content, organization, and Messenger targets.
    """
    if target is None or not getattr(target, "pk", None):
        return False

    model = target.__class__
    locked_target = model._default_manager.select_for_update().filter(pk=target.pk).first()

    if locked_target is None:
        return False

    field_names = _model_field_names(locked_target)
    updates = {}

    if "is_active" in field_names:
        updates["is_active"] = False

    if "is_suspended" in field_names:
        updates["is_suspended"] = True

    if "suspended_at" in field_names:
        updates["suspended_at"] = timezone.now()

    if "suspension_reason" in field_names:
        updates["suspension_reason"] = str(reason or SANCTUARY_CONFIRMED_REASON)[:255]

    if not updates:
        logger.warning(
            "[Sanctuary] Confirmed outcome target has no supported moderation fields: %s:%s",
            locked_target._meta.label_lower,
            locked_target.pk,
        )
        return False

    model._default_manager.filter(pk=locked_target.pk).update(**updates)

    for field_name, value in updates.items():
        setattr(target, field_name, value)

    logger.warning(
        "[Sanctuary] Confirmed moderation enforced target=%s:%s fields=%s",
        locked_target._meta.label_lower,
        locked_target.pk,
        sorted(updates),
    )

    return True