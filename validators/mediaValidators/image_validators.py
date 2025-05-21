from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from validators.mime_type_validator import validate_file_type
import mimetypes

IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image_size(image):
    if image.size > IMAGE_MAX_SIZE:
        raise ValidationError(f"The maximum image file size is {IMAGE_MAX_SIZE / (1024 * 1024)} MB.")

def validate_image_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "image":
        raise ValidationError("Only image files are allowed.")

    if value.name.lower().endswith(".heic"):
        return  

    try:
        value.seek(0)
        image = Image.open(value)
        image.load()
        image.close()
    except Exception:
        raise ValidationError("This file is not a valid image.")

    except Exception as e:
        raise ValidationError(f"Image validation error: {str(e)}")
