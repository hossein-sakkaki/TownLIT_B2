import mimetypes
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type
import ffmpeg
from PIL import Image

# IMAGE & VIDEO Validator ------------------------------------------------------------------------------------------
def validate_image_or_video_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)

    file_type = validate_file_type(value.name, mime_type)

    if file_type == "image":
        try:
            img = Image.open(value)
            img.verify()
        except Exception:
            raise ValidationError("This file is not a valid image.")
    elif file_type == "video":
        try:
            probe = ffmpeg.probe(value.temporary_file_path())
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if not video_stream:
                raise ValidationError("No valid video stream found.")
            frame_rate = eval(video_stream['r_frame_rate'])
            if frame_rate < 24 or frame_rate > 60:
                raise ValidationError(f"Frame rate {frame_rate} is not supported.")
        except Exception as e:
            raise ValidationError(f"Video validation error: {str(e)}")
    else:
        raise ValidationError("Unsupported file type. Only images and videos are allowed.")