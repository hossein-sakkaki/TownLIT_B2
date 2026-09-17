# apps/notifications/utils.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2025-10-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from .constants import (
    GUEST_ALLOWED_NOTIFICATION_TYPES,
    NOTIFICATION_TYPES,
    NOTIFICATION_TYPES_EXCLUDED_FROM_PREFERENCES,
)


def get_allowed_notification_types_for_user(user) -> set[str]:
    """Return user-configurable notification types."""
    all_types = {
        notification_type
        for notification_type, _ in NOTIFICATION_TYPES
    }

    all_types -= NOTIFICATION_TYPES_EXCLUDED_FROM_PREFERENCES

    if getattr(user, "is_member", False):
        return all_types

    return (
        set(GUEST_ALLOWED_NOTIFICATION_TYPES)
        - NOTIFICATION_TYPES_EXCLUDED_FROM_PREFERENCES
    )