from rest_framework import permissions
from apps.profilesOrg.models import OrganizationManager

class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow create for anyone, but list/update only for admins"""
    def has_permission(self, request, view):
        if view.action in ['create']:
            return True
        return request.user and request.user.is_staff


class IsSanctuaryVerifiedMember(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_verified_identity and request.user.is_sanctuary_participant
    
    

class IsFullAccessAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        # Only admins should be able to add services
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Ensure the user has full access to the organization
        try:
            organization_manager = OrganizationManager.objects.get(member=request.user, organization=obj)
            return organization_manager.access_level == OrganizationManager.FULL_ACCESS
        except OrganizationManager.DoesNotExist:
            return False


class IsLimitedAccessAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        # The user must be authenticated
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Check if the user has limited access to the organization
        try:
            organization_manager = OrganizationManager.objects.get(member=request.user, organization=obj)
            return organization_manager.access_level in [OrganizationManager.LIMITED_ACCESS, OrganizationManager.FULL_ACCESS]
        except OrganizationManager.DoesNotExist:
            return False
