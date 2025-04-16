import os

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

        # Videos
        "video/mp4": "video",
        "video/webm": "video",     # for fallback uploads
        "video/ogg": "video",

        # Audio
        "audio/mp4": "audio",      # ✅ m4a for Safari
        "audio/m4a": "audio",      # ✅ custom support
        "audio/webm": "audio",     # for browsers like Chrome
        "audio/mpeg": "audio",
        "audio/wav": "audio",
        "audio/ogg": "audio",

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
    }

    extension_map = {
        # Images
        ".jpg": "image",
        ".jpeg": "image",
        ".png": "image",
        ".gif": "image",
        ".webp": "image",

        # Videos
        ".mp4": "video",
        ".webm": "video",
        ".ogg": "video",

        # Audios
        ".mp3": "audio",
        ".wav": "audio",
        ".ogg": "audio",
        ".m4a": "audio",         # ✅ recommended extension
        ".mp4a": "audio",        # ✅ extra for compatibility

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
    unsafe_ext = [".exe", ".bat", ".sh", ".py", ".php", ".js", ".jar", ".dll"]
    _, ext = os.path.splitext(file_name.lower())
    return ext in unsafe_ext
