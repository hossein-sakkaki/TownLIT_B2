# apps/accounts/mixins.py
from rest_framework.reverse import reverse
from django.conf import settings

class AvatarURLMixin:
    """
    Safe avatar URL generator:
    - If user has NO custom uploaded avatar (or uses default URL) → return DEFAULT_USER_AVATAR_URL
    - Otherwise return versioned proxy URL for S3-backed avatar
    """

    def build_avatar_url(self, user):
        # Fallback if no user object at all
        if not user:
            return settings.DEFAULT_USER_AVATAR_URL

        # Normalize stored value (ImageField or string URL)
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
