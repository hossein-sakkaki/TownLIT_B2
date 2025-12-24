# apps/sanctuary/realtime/utils.py

import re
from django.contrib.contenttypes.models import ContentType

def normalize_content_type(value) -> str:
    """
    Normalize content_type to 'app_label.model'
    Accepts:
      - string
      - ContentType instance
    """
    if isinstance(value, ContentType):
        return f"{value.app_label}.{value.model}"

    if isinstance(value, str):
        return value.strip()

    raise TypeError(f"Invalid content_type: {type(value)}")


def sanitize_group_part(value: str) -> str:
    """
    Make a string safe for Channels group names.
    """
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "_", value)
    return value
