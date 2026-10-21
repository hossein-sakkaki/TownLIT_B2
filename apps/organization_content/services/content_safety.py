# apps/organization_content/services/content_safety.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from apps.content_safety.enums import SafetyContext
from apps.content_safety.services.text import enforce_text_safety


def enforce_update_caption_safety(*, caption, actor, instance=None):
    if instance is not None and caption == instance.caption:
        return
    enforce_text_safety(
        text=caption, context=SafetyContext.GENERIC,
        actor=actor, field_name="caption",
    )
