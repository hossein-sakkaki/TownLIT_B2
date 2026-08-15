#
#  apps/conversation/services/content_safety.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-14.
#  Last Update by Hossein Sakkaki on 2026-08-14.
#

from __future__ import annotations

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety


def enforce_group_message_content_safety(
    *,
    dialogue,
    text,
    actor,
    field_name: str = "content",
) -> None:
    """
    Enforce safety only for backend-readable group messages.

    Private E2EE dialogues must never pass plaintext through
    this service.
    """
    if dialogue is None:
        return

    if not getattr(
        dialogue,
        "is_group",
        False,
    ):
        return

    if not isinstance(
        text,
        str,
    ):
        return

    cleaned = text.strip()

    if not cleaned:
        return

    enforce_text_safety(
        text=cleaned,
        context=SafetyContext.GROUP_MESSAGE,
        actor=actor,
        field_name=field_name,
    )


def enforce_group_metadata_content_safety(
    *,
    text,
    actor,
    field_name: str,
) -> None:
    """
    Enforce safety for group-visible metadata such as
    the group name.
    """
    if not isinstance(
        text,
        str,
    ):
        return

    cleaned = text.strip()

    if not cleaned:
        return

    enforce_text_safety(
        text=cleaned,
        context=SafetyContext.GROUP_TEXT,
        actor=actor,
        field_name=field_name,
    )