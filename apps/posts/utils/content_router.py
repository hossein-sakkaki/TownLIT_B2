from urllib.parse import urlencode

# =====================================================
# UNIVERSAL CONTENT ROUTER (TownLIT)
# =====================================================
def resolve_content_path(
    model_name: str,
    slug: str,
    subtype: str | None = None,
    focus: str | None = None,
    endpoint: str | None = None,
) -> str:
    """
    Build a universal frontend URL for any content type.

    Examples:
      /content/<slug>?type=video&e=/posts/me/testimonies&focus=comment-4
      /content/<slug>?type=video&e=/posts/me/testimonies&focus=reply-12:parent-4
    """

    if not slug:
        return "#"

    # ------------------------------
    # Normalize identifiers
    # ------------------------------
    name = (model_name or "").lower().strip()
    subtype = (subtype or "").lower().strip()

    # ------------------------------
    # Smart content-type detection
    # ------------------------------
    if subtype in {"video", "film", "media"} or name in {"worship", "witness", "moment", "media"}:
        content_type = "video"
    elif subtype in {"voice", "audio", "sound"} or name in {"library", "prayer", "pray", "echo"}:
        content_type = "voice"
    else:
        content_type = "read"

    # ------------------------------
    # Smart endpoint inference
    # ------------------------------
    if not endpoint:
        if name in {"testimony", "witness", "moment"}:
            endpoint = "/posts/me/testimonies"
        elif name in {"lesson", "preach", "announcement"}:
            endpoint = "/posts/me/lessons"
        elif name in {"worship"}:
            endpoint = "/posts/me/worships"
        elif name in {"library"}:
            endpoint = "/posts/me/library"
        else:
            endpoint = "/posts/me/posts"

    # ------------------------------
    # Assemble query parameters
    # ------------------------------
    params = {"type": content_type, "e": endpoint}
    if focus:
        params["focus"] = focus

    query = urlencode(params, doseq=True)
    return f"/content/{slug}?{query}"
