# apps/core/square/constants.py

# =====================================================
# Square content kinds (Tabs)
# =====================================================

SQUARE_KIND_ALL = "all"
SQUARE_KIND_FRIENDS = "friends"
SQUARE_KIND_MOMENT = "moment"
SQUARE_KIND_TESTIMONY = "testimony"
SQUARE_KIND_PRAY = "pray"


SQUARE_CONTENT_KINDS = [
    SQUARE_KIND_ALL,
    SQUARE_KIND_FRIENDS,
    SQUARE_KIND_MOMENT,
    SQUARE_KIND_TESTIMONY,
    SQUARE_KIND_PRAY,
]


# =====================================================
# Media kinds
# =====================================================

MEDIA_VIDEO = "video"
MEDIA_IMAGE = "image"
MEDIA_AUDIO = "audio"


# =====================================================
# Allowed media in Square (phase-based)
# =====================================================
# Phase 1:
#   - video ✅
#   - image ✅ (temporary, removable later)
#
# Phase 2:
#   - video only
# =====================================================

SQUARE_ALLOWED_MEDIA_KINDS = [
    MEDIA_VIDEO,
    MEDIA_IMAGE,   # remove later when feed grows
]

