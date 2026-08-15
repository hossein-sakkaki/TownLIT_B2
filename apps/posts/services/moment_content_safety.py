# apps/posts/services/moment_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety
from apps.posts.models.moment import Moment


def enforce_moment_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: Moment | None = None,
) -> None:
    """
    Enforce Content Safety for created or edited Moment captions.

    Safety runs only when caption is part of the write payload.
    Updates to visibility, cover, thumbnail, or other non-text fields
    do not trigger a Content Safety request.
    """

    if "caption" not in validated_data:
        return

    caption = validated_data.get("caption")

    # Do not re-check an unchanged caption on update.
    if instance is not None and caption == instance.caption:
        return

    enforce_text_safety(
        text=caption,
        context=SafetyContext.MOMENT_CAPTION,
        actor=actor,
        field_name="caption",
    )