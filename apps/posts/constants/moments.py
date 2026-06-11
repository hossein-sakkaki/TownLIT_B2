# apps/posts/constants/moments.py

MOMENT_MEDIA_KIND_IMAGE = "image"
MOMENT_MEDIA_KIND_VIDEO = "video"

MOMENT_MEDIA_KIND_CHOICES = [
    (MOMENT_MEDIA_KIND_IMAGE, "Image"),
    (MOMENT_MEDIA_KIND_VIDEO, "Video"),
]

# Biblical/product limit: a complete visual story.
MOMENT_MAX_IMAGES = 7

# Virtual asset field prefix for JSON-backed images.
MOMENT_IMAGE_ITEMS_FIELD_PREFIX = "image_items"