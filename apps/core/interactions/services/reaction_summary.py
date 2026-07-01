# apps/core/interactions/services/reaction_summary.py

from django.apps import apps
from django.contrib.contenttypes.models import ContentType

from apps.posts.models.reaction import Reaction


def _resolve_model_class(ct: ContentType):
    """
    Resolve a stable model class even if ct.model_class() is None.
    Supports stale/legacy content-type aliases like posts.pray -> posts.Prayer.
    """
    model_class = ct.model_class()
    if model_class is not None:
        return model_class

    try:
        model_class = apps.get_model(ct.app_label, ct.model)
        if model_class is not None:
            return model_class
    except Exception:
        pass

    alias_map = {
        ("posts", "pray"): "Prayer",
        ("posts", "prayerresponse"): "Prayer",
        ("posts", "prayer_response"): "Prayer",
    }

    alias_target = alias_map.get((ct.app_label, ct.model))
    if alias_target:
        try:
            model_class = apps.get_model(ct.app_label, alias_target)
            if model_class is not None:
                return model_class
        except Exception:
            pass

    return None


def build_reaction_summary_payload(*, content_type, object_id, user=None, target_row=None):
    """
    Canonical interaction-style summary payload for API and realtime.
    """
    if target_row is None:
        model_class = _resolve_model_class(content_type)
        if not model_class:
            return None

        target_row = (
            model_class.objects
            .filter(pk=object_id)
            .values("reactions_count", "reactions_breakdown")
            .first()
        )

    if not target_row:
        return None

    my_reaction = None
    if user and getattr(user, "is_authenticated", False):
        my_reaction = (
            Reaction.objects
            .filter(
                content_type=content_type,
                object_id=object_id,
                name=user,
            )
            .values_list("reaction_type", flat=True)
            .first()
        )

    return {
        "content_type": f"{content_type.app_label}.{content_type.model}",
        "object_id": int(object_id),
        "reactions_count": target_row.get("reactions_count") or 0,
        "reactions_breakdown": target_row.get("reactions_breakdown") or {},
        "my_reaction": my_reaction,
    }