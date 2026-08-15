# apps/posts/services/comment_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.services.text import (
    enforce_text_safety,
)
from apps.posts.models.comment import (
    Comment,
)


def enforce_comment_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: Comment | None = None,
) -> None:
    """
    Enforce safety for created or edited comment text.
    """

    if "comment" not in validated_data:
        return

    text = validated_data.get(
        "comment"
    )

    if instance is not None:
        is_reply = bool(
            instance.recomment_id
        )
    else:
        parent = validated_data.get(
            "recomment"
        )

        is_reply = parent is not None

    context = (
        SafetyContext.REPLY
        if is_reply
        else SafetyContext.COMMENT
    )

    enforce_text_safety(
        text=text,
        context=context,
        actor=actor,
        field_name="comment",
    )