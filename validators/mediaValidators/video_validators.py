import os
import ffmpeg
import mimetypes
from tempfile import NamedTemporaryFile
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import TemporaryUploadedFile
from validators.mime_type_validator import validate_file_type

MIN_FRAME_RATE = 24
MAX_FRAME_RATE = 60

def validate_video_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "video":
        raise ValidationError("Only video files are allowed.")

    temp_file_path = None
    is_temp_file = False

    try:
        if isinstance(value, TemporaryUploadedFile):
            temp_file_path = value.temporary_file_path()
        else:
            temp_file = NamedTemporaryFile(delete=False, suffix=".mp4")
            for chunk in value.chunks():
                temp_file.write(chunk)
            temp_file.flush()
            temp_file_path = temp_file.name
            temp_file.close()
            is_temp_file = True

        probe = ffmpeg.probe(temp_file_path)
        stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if not stream:
            raise ValidationError("No valid video stream found.")

        frame_rate = eval(stream['r_frame_rate'])
        if frame_rate < MIN_FRAME_RATE or frame_rate > MAX_FRAME_RATE:
            raise ValidationError(f"Frame rate {frame_rate} is not supported (must be between {MIN_FRAME_RATE} and {MAX_FRAME_RATE}).")

    except Exception as e:
        raise ValidationError(f"Video validation error: {str(e)}")
    
    finally:
        # حذف فایل موقتی فقط اگر خودمان ساخته باشیم
        if is_temp_file and temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
