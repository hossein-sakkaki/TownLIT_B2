# apps/accounts/mixins.py
from rest_framework.reverse import reverse
from django.conf import settings

from apps.asset_delivery.utils.cdn_urls import build_cdn_url


class AvatarURLMixin:
    """
    Safe avatar URLs:
    - avatar_url: versioned proxy endpoint (existing behavior)
    - avatar_cdn_url: clean CDN url (NEW) => media.townlit.com/<storage_key>
    """

    def build_avatar_url(self, user):
        # Existing proxy behavior (keep as-is)
        if not user:
            return settings.DEFAULT_USER_AVATAR_URL

        raw_value = str(getattr(user, "image_name", "") or "")

        default_url = getattr(settings, "DEFAULT_USER_AVATAR_URL", "")
        default_path = "/static/defaults/default-avatar.png"

        if (
            raw_value == "" or
            raw_value == default_url or
            raw_value.endswith(default_path)
        ):
            return default_url or default_path

        request = self.context.get("request")
        if not request:
            return default_url or default_path

        try:
            base = reverse(
                "main:main-avatar-detail",
                args=[user.id],
                request=request,
            )
            version = getattr(user, "avatar_version", 1) or 1
            return f"{base}?v={version}"
        except Exception:
            return default_url or default_path

    def build_avatar_cdn_url(self, user):
        """
        NEW: Clean CDN URL, derived from storage key.
        Returns default avatar if no custom avatar exists.
        """
        if not user:
            return getattr(settings, "DEFAULT_USER_AVATAR_URL", "") or "/static/defaults/default-avatar.png"

        img = getattr(user, "image_name", None)
        # If no file => default
        if not img:
            return getattr(settings, "DEFAULT_USER_AVATAR_URL", "") or "/static/defaults/default-avatar.png"

        # Prefer ImageField.name (always the storage key)
        key = getattr(img, "name", None) or str(img) or ""
        key = key.strip()

        default_url = getattr(settings, "DEFAULT_USER_AVATAR_URL", "")
        default_path = "/static/defaults/default-avatar.png"

        if (key == "" or key == default_url or key.endswith(default_path)):
            return default_url or default_path

        # Build clean CDN URL
        return build_cdn_url(key) or (default_url or default_path)
