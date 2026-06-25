# apps/conversation/services/message_media_descriptors.py

def build_message_media_descriptor(message, field_name, kind):
    """
    Build Asset Delivery descriptor for non-E2EE Messenger media.

    Private E2EE files must stay on the encrypted-media resolver path,
    so we intentionally do not expose descriptors for encrypted file blobs.
    """

    if getattr(message, "is_encrypted_file", False):
        return None

    field = getattr(message, field_name, None)

    if not field:
        return None

    storage_name = getattr(field, "name", None)

    if not storage_name:
        return None

    return {
        "app_label": "conversation",
        "model": "message",
        "object_id": message.id,
        "field_name": field_name,
        "kind": kind,
    }


def build_message_media_descriptors(message):
    """
    Return all Messenger media descriptors in the same shape used by REST.
    """

    return {
        "image_media": build_message_media_descriptor(
            message,
            "image",
            "image",
        ),
        "video_media": build_message_media_descriptor(
            message,
            "video",
            "video",
        ),
        "audio_media": build_message_media_descriptor(
            message,
            "audio",
            "audio",
        ),
        "file_media": build_message_media_descriptor(
            message,
            "file",
            "file",
        ),
    }