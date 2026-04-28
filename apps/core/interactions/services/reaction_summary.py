# apps/core/interactions/services/reaction_summary.py

from django.contrib.contenttypes.models import ContentType
from apps.posts.models.reaction import Reaction


def build_reaction_summary_payload(*, content_type, object_id, user=None, target_row=None):
    """
    Canonical interaction-style summary payload for API and realtime.
    """
    if target_row is None:
        model_class = content_type.model_class()
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