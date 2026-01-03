# apps/sanctuary/services/link_resolver.py

from apps.notifications.services.ui_link_resolver import build_content_link
from apps.posts.models.testimony import Testimony
from apps.posts.models.moment import Moment
from apps.accounts.models import CustomUser
from apps.profilesOrg.models import Organization


def resolve_sanctuary_target_link(req) -> str | None:
    target = getattr(req, "content_object", None)
    if not target:
        return None

    # -------------------------
    # Content (posts)
    # -------------------------
    if isinstance(target, Testimony):
        # Map testimony type -> universal viewer mode
        if getattr(target, "type", None) == Testimony.TYPE_VIDEO:
            mode = "media"
        elif getattr(target, "type", None) == Testimony.TYPE_AUDIO:
            mode = "voice"
        else:
            mode = "read"

        return build_content_link(
            slug=target.slug,
            section="/posts/me/testimonies",
            mode=mode,
        )

    if isinstance(target, Moment):
        # Moments are always media (image/video)
        return build_content_link(
            slug=target.slug,
            section="/posts/me/moments",
            mode="media",
        )

    # -------------------------
    # User account
    # -------------------------
    if isinstance(target, CustomUser):
        return f"/@{target.username}"

    # -------------------------
    # Organization
    # -------------------------
    if isinstance(target, Organization):
        return f"/orgs/{target.slug}"

    return None
