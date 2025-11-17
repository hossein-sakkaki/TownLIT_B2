# apps/conversation/serializers/mixins.py
from rest_framework.reverse import reverse
from django.conf import settings

class GroupAvatarURLMixin:
    """
    Safe group avatar URL generator:
    - If no custom group_image → return DEFAULT_GROUP_AVATAR_URL.
    - If stored value equals default → also return DEFAULT_GROUP_AVATAR_URL.
    - Otherwise → return versioned proxy URL.
    """

    def get_group_avatar_url(self, obj):
        # Only for group chats
        if not getattr(obj, "is_group", False):
            return None

        # Normalize stored value (ImageField or string URL)
        raw_value = str(getattr(obj, "group_image", "") or "")

        default_url = getattr(settings, "DEFAULT_GROUP_AVATAR_URL", "")
        default_path = "/static/defaults/default-group-avatar.png"

        # CASE 1 › no image at all
        if raw_value == "":
            return default_url or default_path

        # CASE 2 › value equals default URL (this happens when you set default manually)
        if raw_value == default_url:
            return default_url

        # CASE 3 › value matches path of default image
        if raw_value.endswith(default_path):
            return default_url or default_path

        # Otherwise › it's a real uploaded group avatar → use proxy
        request = self.context.get("request")
        if not request:
            return default_url or default_path

        try:
            base = reverse(
                "main:main-group-avatar-detail",
                args=[obj.id],
                request=request,
            )
            version = getattr(obj, "group_avatar_version", 1) or 1
            return f"{base}?v={version}"
        except Exception:
            # fail-safe (never break client)
            return default_url or default_path
