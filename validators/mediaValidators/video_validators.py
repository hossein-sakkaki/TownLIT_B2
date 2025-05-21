import ffmpeg
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type
import mimetypes
from tempfile import NamedTemporaryFile

MIN_FRAME_RATE = 24
MAX_FRAME_RATE = 60

def validate_video_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "video":
        raise ValidationError("Only video files are allowed.")

    try:
        with NamedTemporaryFile(delete=False, suffix=".mp4") as temp:
            for chunk in value.chunks():
                temp.write(chunk)
            temp.flush()

            probe = ffmpeg.probe(temp.name)
            stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
            if not stream:
                raise ValidationError("No valid video stream found.")

            frame_rate = eval(stream['r_frame_rate'])
            if frame_rate < MIN_FRAME_RATE or frame_rate > MAX_FRAME_RATE:
                raise ValidationError(f"Frame rate {frame_rate} is not supported (must be between {MIN_FRAME_RATE} and {MAX_FRAME_RATE}).")

    except Exception as e:
        raise ValidationError(f"Video validation error: {str(e)}")
