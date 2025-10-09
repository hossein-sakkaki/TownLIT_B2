# apps/core/permissions.py
from rest_framework.permissions import BasePermission
from .api_exceptions import SuspendedAccount, DeletedAccount

class DenyIfDeletedOrSuspended(BasePermission):
    """
    Block authenticated users if deleted/suspended unless the action is whitelisted on the view.
    Views may define:
      - allow_deleted_actions = {'send_reactivate_confirmation', 'confirm_reactivate_account', ...}
      - allow_suspended_actions = {'logout', ...}
    """

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return True

        action = getattr(view, "action", None)
        allow_deleted_actions = getattr(view, "allow_deleted_actions", set())
        allow_suspended_actions = getattr(view, "allow_suspended_actions", set())

        if getattr(user, "is_suspended", False):
            if action not in allow_suspended_actions:
                raise SuspendedAccount()

        if getattr(user, "is_deleted", False):
            if action not in allow_deleted_actions:
                raise DeletedAccount()

        return True
