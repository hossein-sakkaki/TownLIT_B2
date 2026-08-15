#
# apps/profiles/services/profile_avatar_content_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-15.
# Last Update by Hossein Sakkaki on 2026-08-15.
#

from __future__ import annotations

from rest_framework import serializers

from apps.content_safety.enums import (
    SafetyContext,
)
from apps.content_safety.services.image import (
    enforce_image_file_safety,
)


def _rewind_uploaded_file(
    file_obj,
) -> None:
    """
    Restore the uploaded file position after Content Safety inspection.

    The same uploaded file is persisted to CustomUser.image_name after
    Safety succeeds, so the storage layer must receive the file from
    the beginning regardless of how the safety pipeline consumed it.
    """

    if file_obj is None:
        return

    seek = getattr(
        file_obj,
        "seek",
        None,
    )

    if not callable(
        seek
    ):
        return

    try:
        seek(
            0
        )
    except Exception:
        # Rewind is best-effort here.
        # Any actual persistence failure will still surface normally.
        pass


def enforce_profile_avatar_content_safety(
    *,
    file_obj,
    actor,
) -> None:
    """
    Require a newly uploaded personal avatar to pass Image Safety
    before replacing CustomUser.image_name.

    Applies equally to:
    - Member profile avatar
    - Guest profile avatar

    The publication policy uses PROFILE_MEDIA because an avatar is
    profile media. `avatar` is retained as the audit field name so
    safety events remain semantically clear.

    Content Safety exceptions intentionally propagate unchanged so
    clients receive the standard TownLIT Content Safety envelope.

    Invalid media-shape errors are returned as normal field validation
    errors for the multipart `profile_image` input.
    """

    if not file_obj:
        return

    try:
        try:
            enforce_image_file_safety(
                file_obj=file_obj,
                context=SafetyContext.PROFILE_MEDIA,
                actor=actor,
                field_name="avatar",
                mime_type=getattr(
                    file_obj,
                    "content_type",
                    None,
                ),
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise serializers.ValidationError(
                {
                    "profile_image": str(
                        exc
                    ),
                }
            ) from exc

    finally:
        _rewind_uploaded_file(
            file_obj
        )