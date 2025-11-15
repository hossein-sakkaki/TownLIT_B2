# apps/accounts/mixins.py
from rest_framework.reverse import reverse

class AvatarURLMixin:
    """
    Provides a reusable helper for generating versioned avatar URLs.
    - Adds cache-busting using avatar_version
    - Always respects request context
    """

    def build_avatar_url(self, user):
        request = self.context.get("request")
        if not request or not user:
            return None

        # Base proxy endpoint
        base = reverse(
            "main:main-avatar-detail",
            args=[user.id],
            request=request
        )

        # cache-buster v=<int>
        version = getattr(user, "avatar_version", 1)
        return f"{base}?v={version}"
