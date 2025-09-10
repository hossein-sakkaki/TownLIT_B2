# apps/posts/permissions.py

from rest_framework import permissions
from django.contrib.contenttypes.models import ContentType
from apps.profiles.models import Member
from apps.posts.models import Testimony

class IsOwnerOfMemberTestimony(permissions.BasePermission):
    """
    Allow access only to testimonies owned by the authenticated user's Member.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj: Testimony):
        if not isinstance(obj, Testimony):
            return False
        ct_member = ContentType.objects.get_for_model(Member)
        if obj.content_type_id != ct_member.id:
            return False
        member = getattr(request.user, 'member_profile', None) or getattr(request.user, 'member', None)
        return bool(member and obj.object_id == member.id)
