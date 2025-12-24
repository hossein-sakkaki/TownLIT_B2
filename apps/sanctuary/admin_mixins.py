# apps/sanctuary/admin_mixins.py

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from apps.sanctuary.services.protection import is_edit_locked


# Mixin to block updates when Sanctuary protection is active --------------------------------------------
class SanctuaryEditLockAdminMixin:
    """
    If target has active protection label:
    - Update is blocked (even for superuser)
    - Delete remains allowed
    - Admin can still view the change page (read-only)
    """

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and is_edit_locked(obj):
            # Make everything read-only
            all_fields = [f.name for f in obj._meta.fields]
            ro = list(set(ro + all_fields))
        return ro

    def save_model(self, request, obj, form, change):
        if change and obj and is_edit_locked(obj):
            # Block all updates
            raise PermissionDenied("This item is locked by Sanctuary protection label.")
        return super().save_model(request, obj, form, change)

    def response_change(self, request, obj):
        if obj and is_edit_locked(obj):
            messages.warning(request, "🔒 Locked by Sanctuary label: updates are blocked. Delete is allowed.")
        return super().response_change(request, obj)
