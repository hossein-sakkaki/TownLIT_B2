# validators/mediaValidators/conversation_upload_limits.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-18.
# Last Update by Hossein Sakkaki on 2026-10-18.
#

"""Messenger-specific media size policy; MIME and malware guards remain shared."""

from __future__ import annotations

from django.conf import settings


_DEFAULT_LIMITS_BYTES = {
    "image": 20 * 1024 * 1024,
    "video": 250 * 1024 * 1024,
    "audio": 35 * 1024 * 1024,
    "file": 50 * 1024 * 1024,
}

_SETTINGS_BY_MEDIA_FIELD = {
    "image": "CONVERSATION_MEDIA_IMAGE_MAX_BYTES",
    "video": "CONVERSATION_MEDIA_VIDEO_MAX_BYTES",
    "audio": "CONVERSATION_MEDIA_AUDIO_MAX_BYTES",
    "file": "CONVERSATION_MEDIA_FILE_MAX_BYTES",
}


def conversation_media_max_bytes(field_name: str) -> int:
    """Resolve authoritative server policy once for all Conversation contexts."""
    name = str(field_name or "").strip().lower()
    setting_name = _SETTINGS_BY_MEDIA_FIELD.get(name)
    if setting_name is None:
        raise ValueError("Unsupported Messenger media field.")

    value = int(getattr(settings, setting_name, _DEFAULT_LIMITS_BYTES[name]))
    if value <= 0:
        raise ValueError(f"{setting_name} must be positive.")
    return value


def validate_conversation_media_size(*, uploaded_file, field_name: str) -> dict:
    """Check size after shared MIME/safety validation, before media persistence."""
    maximum = conversation_media_max_bytes(field_name)
    actual = int(getattr(uploaded_file, "size", 0) or 0)
    if 0 < actual <= maximum:
        return {"ok": True, "max_bytes": maximum}

    if actual <= 0:
        return {
            "ok": False,
            "code": "EMPTY_FILE",
            "message": "The uploaded file is empty.",
            "status": 400,
            "max_bytes": maximum,
            "actual_bytes": actual,
        }

    label = str(field_name).capitalize()
    maximum_mb = maximum / (1024 * 1024)
    maximum_text = f"{maximum_mb:g}"
    return {
        "ok": False,
        "code": "FILE_TOO_LARGE",
        "message": f"{label} exceeds the {maximum_text} MB Messenger upload limit.",
        "status": 413,
        "max_bytes": maximum,
        "actual_bytes": actual,
    }
