# apps/accounts/permissions.py

from rest_framework.permissions import BasePermission

class IsAdminUserStrict(BasePermission):
    # Allow only platform admins
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)
