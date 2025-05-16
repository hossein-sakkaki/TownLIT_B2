from rest_framework import permissions




class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow create for anyone, but list/update only for admins"""
    def has_permission(self, request, view):
        if view.action in ['create']:
            return True
        return request.user and request.user.is_staff
