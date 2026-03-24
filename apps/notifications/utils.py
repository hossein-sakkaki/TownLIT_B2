# apps/notifications/utils.py

from .constants import (
    NOTIFICATION_TYPES,
    GUEST_ALLOWED_NOTIFICATION_TYPES,
)


def get_allowed_notification_types_for_user(user) -> set[str]:
    """
    Return the notification types that are valid for the user's active profile.

    Member users keep access to all current notification types.
    Guest users are restricted to guest-safe notification types only.
    """
    all_types = {notif_type for notif_type, _ in NOTIFICATION_TYPES}

    if getattr(user, "is_member", False):
        return all_types

    return set(GUEST_ALLOWED_NOTIFICATION_TYPES)