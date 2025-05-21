import ffmpeg
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type
import mimetypes

ALLOWED_AUDIO_CODECS = ['aac', 'mp3', 'vorbis', 'opus']
MIN_BITRATE = 128000
MAX_BITRATE = 320000

def validate_audio_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "audio":
        raise ValidationError("Only audio files are allowed.")

    try:
        probe = ffmpeg.probe(value.temporary_file_path())
        stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)
        if not stream:
            raise ValidationError("No audio stream found.")
        codec = stream.get('codec_name')
        if codec not in ALLOWED_AUDIO_CODECS:
            raise ValidationError(f"Unsupported audio codec: {codec}")
        bitrate = int(stream.get('bit_rate', 0))
        if bitrate < MIN_BITRATE or bitrate > MAX_BITRATE:
            raise ValidationError(f"Audio bitrate {bitrate} not supported.")
    except Exception as e:
        raise ValidationError(f"Invalid audio file: {str(e)}")
