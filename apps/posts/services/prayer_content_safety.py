# apps/posts/services/prayer_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety
from apps.posts.models.pray import Prayer, PrayerResponse


def enforce_prayer_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: Prayer | None = None,
) -> None:
    """
    Enforce Content Safety for created or edited Prayer text.

    Safety runs only when caption is part of the write payload.
    Non-text updates do not trigger another safety request.
    """

    if "caption" not in validated_data:
        return

    caption = validated_data.get("caption")

    if instance is not None and caption == instance.caption:
        return

    enforce_text_safety(
        text=caption,
        context=SafetyContext.PRAYER,
        actor=actor,
        field_name="caption",
    )


def enforce_prayer_response_content_safety(
    *,
    validated_data: dict,
    actor,
    instance: PrayerResponse | None = None,
) -> None:
    """
    Enforce Content Safety for created or edited Prayer response text.

    Prayer responses share the Prayer safety context so supportive
    discussion of distress, trauma, addiction, or self-harm remains
    context-aware rather than being blocked solely by topic.
    """

    if "response_text" not in validated_data:
        return

    response_text = validated_data.get("response_text")

    if (
        instance is not None
        and response_text == instance.response_text
    ):
        return

    enforce_text_safety(
        text=response_text,
        context=SafetyContext.PRAYER,
        actor=actor,
        field_name="response_text",
    )