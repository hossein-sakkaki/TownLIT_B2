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
        return build_content_link(
            slug=target.slug,
            section="/posts/me/testimonies",
        )

    if isinstance(target, Moment):
        return build_content_link(
            slug=target.slug,
            section="/posts/me/moments",
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
