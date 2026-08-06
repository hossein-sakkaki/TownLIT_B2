# apps/accounts/permissions.py

from rest_framework.permissions import BasePermission


def is_platform_admin(user) -> bool:
    """
    Central TownLIT platform-admin check.

    Supports the native TownLIT fields and Django compatibility property.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    return bool(
        getattr(user, "is_admin", False)
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )


class IsAdminUserStrict(BasePermission):
    """
    Allow only authenticated TownLIT platform administrators.
    """

    message = "Platform administrator access is required."

    def has_permission(self, request, view) -> bool:
        return is_platform_admin(
            getattr(request, "user", None)
        )