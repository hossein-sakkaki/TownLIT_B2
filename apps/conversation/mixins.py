# apps/conversation/serializers/mixins.py
from rest_framework.reverse import reverse
from django.conf import settings

from apps.asset_delivery.utils.cdn_urls import build_cdn_url


class GroupAvatarURLMixin:
    """
    - group_avatar_url: proxy endpoint (existing behavior)
    - group_avatar_cdn_url: clean CDN url (NEW)
    """

    def get_group_avatar_url(self, obj):
        if not getattr(obj, "is_group", False):
            return None

        raw_value = str(getattr(obj, "group_image", "") or "")

        default_url = getattr(settings, "DEFAULT_GROUP_AVATAR_URL", "")
        default_path = "/static/defaults/default-group-avatar.png"

        if raw_value == "":
            return default_url or default_path

        if raw_value == default_url:
            return default_url

        if raw_value.endswith(default_path):
            return default_url or default_path

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
            return default_url or default_path

    def get_group_avatar_cdn_url(self, obj):
        """
        NEW: Clean CDN URL from storage key (group_image.name).
        """
        if not getattr(obj, "is_group", False):
            return None

        img = getattr(obj, "group_image", None)
        default_url = getattr(settings, "DEFAULT_GROUP_AVATAR_URL", "")
        default_path = "/static/defaults/default-group-avatar.png"

        if not img:
            return default_url or default_path

        key = getattr(img, "name", None) or str(img) or ""
        key = key.strip()

        if key == "" or key == default_url or key.endswith(default_path):
            return default_url or default_path

        return build_cdn_url(key) or (default_url or default_path)
