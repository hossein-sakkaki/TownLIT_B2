import os
import mimetypes


def validate_file_type(file_name: str, content_type: str) -> str | None:
    """
    Return 'image', 'video', 'audio', or 'file' if the type is accepted.
    Otherwise, return None.
    """
    allowed_mime_types = {
        # Images
        "image/jpeg": "image",
        "image/png": "image",
        "image/gif": "image",
        "image/webp": "image",
        "image/heic": "image",
        "image/heif": "image",
        "image/tiff": "image",
        "image/x-tiff": "image",
        "image/x-icon": "image",

        # Videos
        "video/mp4": "video",
        "video/webm": "video",
        "video/ogg": "video",
        "video/quicktime": "video",         # .mov
        "video/x-msvideo": "video",         # .avi
        "video/x-matroska": "video",        # .mkv

        # Audio
        "audio/mp4": "audio",
        "audio/m4a": "audio",
        "audio/x-m4a": "audio",
        "audio/webm": "audio",
        "audio/mpeg": "audio",
        "audio/wav": "audio",
        "audio/ogg": "audio",
        "audio/flac": "audio",
        "audio/aac": "audio",

        # Files
        "application/pdf": "file",
        "application/zip": "file",
        "application/x-zip-compressed": "file",
        "application/msword": "file",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "file",
        "application/vnd.ms-excel": "file",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "file",
        "application/vnd.ms-powerpoint": "file",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "file",
        "text/plain": "file",
        "text/markdown": "file",
        "application/json": "file",
        "application/xml": "file",
    }

    extension_map = {
        # Images
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image",
        ".gif": "image",
        ".webp": "image",
        ".heic": "image",
        ".heif": "image",
        ".tif": "image",
        ".tiff": "image",
        ".ico": "image",

        # Videos
        ".mp4": "video",
        ".webm": "video",
        ".ogg": "video",
        ".mov": "video",
        ".avi": "video",
        ".mkv": "video",

        # Audio
        ".mp3": "audio",
        ".wav": "audio",
        ".ogg": "audio",
        ".m4a": "audio",
        ".mp4a": "audio",
        ".flac": "audio",
        ".aac": "audio",

        # Files
        ".pdf": "file",
        ".zip": "file",
        ".txt": "file",
        ".doc": "file",
        ".docx": "file",
        ".xls": "file",
        ".xlsx": "file",
        ".ppt": "file",
        ".pptx": "file",
        ".md": "file",
        ".json": "file",
        ".xml": "file",
    }

    # First check MIME type
    kind = allowed_mime_types.get(content_type)

    # Fallback to file extension
    if not kind:
        _, ext = os.path.splitext(file_name.lower())
        kind = extension_map.get(ext)

    return kind


def is_unsafe_file(file_name: str) -> bool:
    """
    Reject potentially dangerous extensions
    """
    unsafe_ext = [
        ".exe", ".bat", ".sh", ".py", ".php", ".js",
        ".jar", ".dll", ".com", ".msi", ".vbs", ".wsf", ".scr"
    ]
    _, ext = os.path.splitext(file_name.lower())
    return ext in unsafe_ext
