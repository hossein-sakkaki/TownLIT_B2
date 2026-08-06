# apps/posts/utils/content_router.py

from __future__ import annotations

from urllib.parse import urlencode


CONTENT_ENDPOINTS = {
    "testimony": "/posts/me/testimonies",
    "witness": "/posts/me/testimonies",
    "moment": "/posts/me/moments",
    "prayer": "/posts/me/prayers",
    "pray": "/posts/me/prayers",
    "journey": "/posts/me/journeys",
    "journeyentry": "/posts/me/journeys",
    "lesson": "/posts/me/lessons",
    "preach": "/posts/me/lessons",
    "announcement": "/posts/me/lessons",
    "worship": "/posts/me/worships",
    "library": "/posts/me/library",
}


VIDEO_SUBTYPES = {"video", "film", "media"}
AUDIO_SUBTYPES = {"voice", "audio", "sound"}
WRITTEN_SUBTYPES = {"written", "text", "read"}


def _resolve_viewer_type(model_name: str, subtype: str) -> str:
    """
    Resolve the universal content viewer mode.
    """
    if subtype in VIDEO_SUBTYPES:
        return "video"

    if subtype in AUDIO_SUBTYPES:
        return "voice"

    if subtype in WRITTEN_SUBTYPES:
        return "read"

    if model_name in {"moment", "worship", "media", "journey", "journeyentry"}:
        return "media"

    if model_name in {"library", "echo"}:
        return "voice"

    # Prayer always has an image and may also include video.
    if model_name in {"prayer", "pray"}:
        return "media"

    return "read"


def resolve_content_path(
    model_name: str,
    slug: str,
    subtype: str | None = None,
    focus: str | None = None,
    endpoint: str | None = None,
) -> str:
    """
    Build a universal TownLIT content URL.

    Examples:
      /content/<slug>?type=media&e=/posts/me/moments&focus=comment-4
      /content/<slug>?type=voice&e=/posts/me/testimonies&focus=reply-12:parent-4
    """
    slug = str(slug or "").strip()
    if not slug:
        return "#"

    name = str(model_name or "").strip().lower()
    normalized_subtype = str(subtype or "").strip().lower()

    viewer_type = _resolve_viewer_type(
        model_name=name,
        subtype=normalized_subtype,
    )

    resolved_endpoint = (
        str(endpoint).strip()
        if endpoint
        else CONTENT_ENDPOINTS.get(name, "/posts/me/posts")
    )

    params = {
        "type": viewer_type,
        "e": resolved_endpoint,
    }

    normalized_focus = str(focus or "").strip()
    if normalized_focus:
        params["focus"] = normalized_focus

    return f"/content/{slug}?{urlencode(params)}"