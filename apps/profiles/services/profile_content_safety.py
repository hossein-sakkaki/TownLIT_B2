#
#  apps/profiles/services/profile_content_safety.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-08-14.
#  Last Update by Hossein Sakkaki on 2026-08-14.
#

from __future__ import annotations

from typing import Any

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety


def enforce_member_profile_content_safety(
    *,
    validated_data: dict[str, Any],
    actor,
    instance,
) -> None:
    """
    Enforce Content Safety for editable Member profile text.

    Only fields supplied with a changed value are inspected.
    Clearing an existing field remains allowed without calling
    the moderation provider.
    """

    _enforce_changed_profile_text(
        validated_data=validated_data,
        actor=actor,
        instance=instance,
        fields=(
            "biography",
            "vision",
        ),
    )


def enforce_guest_profile_content_safety(
    *,
    validated_data: dict[str, Any],
    actor,
    instance,
) -> None:
    """
    Enforce Content Safety for editable Guest profile text.
    """

    _enforce_changed_profile_text(
        validated_data=validated_data,
        actor=actor,
        instance=instance,
        fields=(
            "biography",
        ),
    )


def _enforce_changed_profile_text(
    *,
    validated_data: dict[str, Any],
    actor,
    instance,
    fields: tuple[str, ...],
) -> None:
    for field_name in fields:
        if field_name not in validated_data:
            continue

        incoming_value = validated_data.get(
            field_name
        )

        current_value = getattr(
            instance,
            field_name,
            None,
        )

        if incoming_value == current_value:
            continue

        if not _has_meaningful_text(
            incoming_value
        ):
            continue

        enforce_text_safety(
            text=incoming_value,
            context=SafetyContext.PROFILE_TEXT,
            actor=actor,
            field_name=field_name,
        )


def _has_meaningful_text(
    value: Any,
) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
    )