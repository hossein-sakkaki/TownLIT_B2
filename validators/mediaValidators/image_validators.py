from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from validators.mime_type_validator import validate_file_type
import mimetypes
from io import BytesIO

IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image_size(image):
    if image.size > IMAGE_MAX_SIZE:
        raise ValidationError(f"The maximum image file size is {IMAGE_MAX_SIZE / (1024 * 1024)} MB.")

def validate_image_file(value):
    # Skip validation if value is not an uploaded file
    # (e.g., default avatar path as string)
    if not hasattr(value, "file") or not hasattr(value, "read"):
        return

    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "image":
        raise ValidationError("Only image files are allowed.")

    if value.name.lower().endswith(".heic"):
        return

    try:
        image_bytes = BytesIO(value.read())
        image = Image.open(image_bytes)
        image.verify()

    except (UnidentifiedImageError, OSError):
        raise ValidationError("This file is not a valid image.")
    except Exception as e:
        raise ValidationError(f"Image validation error: {str(e)}")
    finally:
        value.seek(0)
