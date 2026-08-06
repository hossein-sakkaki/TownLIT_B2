# apps/sanctuary/services/link_resolver.py

from __future__ import annotations

import logging

from apps.accounts.models.user import CustomUser
from apps.notifications.services.ui_link_resolver import build_content_link
from apps.posts.models.comment import Comment
from apps.posts.models.moment import Moment
from apps.posts.models.testimony import Testimony
from apps.profilesOrg.models import Organization

logger = logging.getLogger(__name__)


def _safe_absolute_url(target) -> str | None:
    resolver = getattr(target, "get_absolute_url", None)

    if not callable(resolver):
        return None

    try:
        value = str(resolver() or "").strip()

        if not value or value == "#":
            return None

        return value

    except Exception:
        logger.exception(
            "[Sanctuary] Target absolute URL resolution failed.",
            extra={
                "target_model": (
                    target._meta.label_lower
                    if hasattr(target, "_meta")
                    else type(target).__name__
                ),
                "target_id": getattr(target, "pk", None),
            },
        )
        return None


def resolve_sanctuary_target_link(req) -> str | None:
    target = getattr(req, "content_object", None)

    if target is None:
        return None

    # Comment and Reply both use posts.comment.
    # Comment.get_absolute_url() includes the exact focus identifier.
    if isinstance(target, Comment):
        return _safe_absolute_url(target)

    # Testimony universal viewer.
    if isinstance(target, Testimony):
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

    # Moment universal viewer.
    if isinstance(target, Moment):
        return build_content_link(
            slug=target.slug,
            section="/posts/me/moments",
            mode="media",
        )

    # Account.
    if isinstance(target, CustomUser):
        return f"/@{target.username}"

    # Organization.
    if isinstance(target, Organization):
        return f"/orgs/{target.slug}"

    # Prayer, JourneyEntry and Messenger group can use their model-level
    # get_absolute_url() when available. We deliberately do not guess routes.
    return _safe_absolute_url(target)