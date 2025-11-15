# apps/conversation/serializers/mixins.py

from rest_framework.reverse import reverse


class GroupAvatarURLMixin:
    """
    Provides a dynamic proxy URL for group avatars.
    Uses:
      - Dialogue.id for endpoint
      - Dialogue.group_avatar_version for cache-busting
      - DRF reverse() with request context (supports HTTPS / domains)
    """
    def get_group_avatar_url(self, obj):
        # Only applies to group dialogues
        if not getattr(obj, "is_group", False):
            return None

        request = self.context.get("request")
        if not request:
            return None

        try:
            base = reverse(
                "main:main-group-avatar-detail",
                args=[obj.id],
                request=request,
            )
        except Exception:
            # fail-safe, don't break serializer
            return None

        version = getattr(obj, "group_avatar_version", 1)
        return f"{base}?v={version}"
