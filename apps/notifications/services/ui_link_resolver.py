# apps/notifications/services/ui_link_resolver.py
from urllib.parse import urlencode, quote


def build_content_link(*, slug: str, section: str, focus: str | None = None) -> str:
    """
    Build frontend-safe deep-link for content pages.

    Examples:
      /content/asdc?type=read&e=/posts/me/testimonies
      /content/asdc?type=read&e=/posts/me/testimonies&focus=comment-334
    """
    params = {
        "type": "read",
        "e": section,
    }

    if focus:
        params["focus"] = focus

    return f"/content/{slug}?{urlencode(params)}"
