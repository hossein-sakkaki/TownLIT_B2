from django.core.exceptions import ValidationError
import ffmpeg
import mimetypes
from PIL import Image
import fitz  # PyMuPDF
import re
import os
from django.core.validators import validate_email
from .mime_type_validator import validate_file_type



# VALIDATORS Manager --------------------------------------------------
ALLOWED_CODECS = ['h264', 'vp8', 'vp9', 'hevc']
MIN_FRAME_RATE = 24
MAX_FRAME_RATE = 60
ALLOWED_AUDIO_CODECS = ['aac', 'mp3', 'vorbis', 'opus']
MIN_BITRATE = 128000
MAX_BITRATE = 320000 
IMAGE_MAX_SIZE = 5 * 1024 * 1024  # 5MB

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


# IMAGE SIZE Validator ---------------------------------------------------------------------------------------------------
def validate_image_size(image):    
    if image.size > IMAGE_MAX_SIZE:
        raise ValidationError(f"The maximum file size that can be uploaded is {max_size / (1024 * 1024)} MB.")

    
# AUDIO Validator ---------------------------------------------------------------------------------------------------
def validate_audio_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "audio":
        raise ValidationError("Only audio files are allowed.")

    try:
        probe = ffmpeg.probe(value.temporary_file_path())
        audio_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'audio']

        if not audio_streams:
            raise ValidationError("No audio streams found.")

        audio_codec = audio_streams[0].get('codec_name')
        if audio_codec not in ALLOWED_AUDIO_CODECS:
            raise ValidationError(
                f"Unsupported audio codec: {audio_codec}. Supported codecs: {', '.join(ALLOWED_AUDIO_CODECS)}"
            )

        bitrate = int(audio_streams[0].get('bit_rate', 0))
        if bitrate < MIN_BITRATE or bitrate > MAX_BITRATE:
            raise ValidationError(
                f"Bitrate {bitrate} not supported. Allowed: {MIN_BITRATE // 1000}–{MAX_BITRATE // 1000} kbps."
            )

    except ffmpeg.Error as e:
        raise ValidationError(f"Error processing audio file: {str(e)}")
    except Exception as e:
        raise ValidationError(f"Invalid audio file: {str(e)}")



# PDF Validator -------------------------------------------------------------------------------------------------------
def validate_pdf_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)

    if file_type != "file":
        raise ValidationError("Only PDF files are allowed.")

    max_file_size_mb = 10
    if value.size > max_file_size_mb * 1024 * 1024:
        raise ValidationError(f"File exceeds {max_file_size_mb}MB.")

    try:
        pdf_document = fitz.open(stream=value.read(), filetype="pdf")
    except Exception as e:
        raise ValidationError(f"Invalid PDF file: {str(e)}")

    if pdf_document.page_count == 0:
        raise ValidationError("PDF file is empty.")
    if pdf_document.is_encrypted:
        raise ValidationError("Encrypted PDFs are not allowed.")
    if pdf_document.pdf_version < '1.4':
        raise ValidationError("Minimum supported PDF version is 1.4.")



# ENTENTIONS Validator -------------------------------------------------------------------------------------------------
def validate_no_executable_file(value):
    disallowed_extensions = ['.exe', '.bat', '.sh', '.dll', '.com']
    extension = os.path.splitext(value.name)[1].lower()
    
    if extension in disallowed_extensions:
        raise ValidationError(f"Executable files are not allowed. Disallowed extensions: {', '.join(disallowed_extensions)}.")


# PHONE NUMBER Validator -----------------------------------------------------------------------------------------------
def validate_phone_number(value):
    """
    Validates phone numbers according to the E.164 international standard.
    Phone number must:
    - Start with an optional '+' (international format)
    - Followed by a country code (1-3 digits) and subscriber number
    - Contain only digits (maximum length of 15 digits, including country code)
    """
    pattern = r'^\+?[1-9]\d{1,14}$'
    if not re.fullmatch(pattern, value):
        raise ValidationError(
            "Phone number must be in international format (e.g., +123456789) and contain only digits."
        )
        
    
        
        

# Email Validator ----------------------------------------------------------------------------------------------------------
def validate_email_field(value):
    try:
        validate_email(value)
    except ValidationError:
        raise ValidationError("Invalid email format.")

# Password Validator -------------------------------------------------------------------------------------------------------
def validate_password_field(value):
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in value):
        raise ValidationError("Password must contain at least one digit.")
    if not any(char.isalpha() for char in value):
        raise ValidationError("Password must contain at least one letter.")
