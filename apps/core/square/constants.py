# apps/core/square/constants.py

# =====================================================
# Square content kinds
# =====================================================

SQUARE_KIND_ALL = "all"

# Legacy request compatibility only.
# Old clients may still send `kind=friends`.
# It must resolve to the unified Square feed.
SQUARE_KIND_FRIENDS = "friends"

SQUARE_KIND_MOMENT = "moment"
SQUARE_KIND_TESTIMONY = "testimony"
SQUARE_KIND_PRAY = "pray"


SQUARE_CONTENT_KINDS = [
    SQUARE_KIND_ALL,
    SQUARE_KIND_MOMENT,
    SQUARE_KIND_TESTIMONY,
    SQUARE_KIND_PRAY,
]


SQUARE_FRIEND_AFFINITY_FIELD = "square_is_friend_owner"


def normalize_square_kind(kind: str | None) -> str:
    normalized = (kind or "").strip().lower()

    if not normalized:
        return SQUARE_KIND_ALL

    if normalized == SQUARE_KIND_FRIENDS:
        return SQUARE_KIND_ALL

    return normalized


# =====================================================
# Media kinds
# =====================================================

MEDIA_VIDEO = "video"
MEDIA_IMAGE = "image"
MEDIA_AUDIO = "audio"


# =====================================================
# Allowed media in Square
# =====================================================

SQUARE_ALLOWED_MEDIA_KINDS = [
    MEDIA_VIDEO,
    MEDIA_IMAGE,
]