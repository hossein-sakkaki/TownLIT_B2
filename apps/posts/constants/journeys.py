# apps/posts/constants/journeys.py

from django.db import models


JOURNEY_MAX_ENTRIES_PER_DAY = 12

JOURNEY_DEFAULT_DURATION_MS = 15_000
JOURNEY_MIN_DURATION_MS = 15_000
JOURNEY_MAX_DURATION_MS = 60_000

JOURNEY_ACTIVE_DURATION_HOURS = 24

JOURNEY_CANVAS_WIDTH = 1080
JOURNEY_CANVAS_HEIGHT = 1920

JOURNEY_MEDIA_DURATION_TOLERANCE_MS = 250

class JourneyEntryMediaType(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"
    
    # Reserved for future releases.
    SHARED_CONTENT = "shared_content", "Shared Content"


class JourneyRetentionPolicy(models.TextChoices):
    KEEP = "keep", "Keep in Journey archive"
    DELETE_AFTER_EXPIRY = (
        "delete_after_expiry",
        "Delete after expiry",
    )


class JourneyVisualSourceType(models.TextChoices):
    UPLOADED_IMAGE = (
        "uploaded_image",
        "Uploaded Image",
    )
    CONTENT_REFERENCE = (
        "content_reference",
        "Content Reference",
    )
    SOLID_BACKGROUND = (
        "solid_background",
        "Solid Background",
    )
    GRADIENT_BACKGROUND = (
        "gradient_background",
        "Gradient Background",
    )
    PRESET_BACKGROUND = (
        "preset_background",
        "Preset Background",
    )


class JourneyPaletteMode(models.TextChoices):
    DAWN = "dawn", "Dawn"
    EVENING = "evening", "Evening"


class JourneyViewSource(models.TextChoices):
    AVATAR_RING = "avatar_ring", "Avatar Ring"
    PROFILE_ARCHIVE = (
        "profile_archive",
        "Profile Archive",
    )
    JOURNEY_STREAM = (
        "journey_stream",
        "Journey Stream",
    )
    DEEP_LINK = "deep_link", "Deep Link"
    OTHER = "other", "Other"