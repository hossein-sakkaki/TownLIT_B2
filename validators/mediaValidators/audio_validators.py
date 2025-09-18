# validators/audio_validator.py
import os
import mimetypes
import ffmpeg
from tempfile import NamedTemporaryFile
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type

ALLOWED_AUDIO_CODECS = {'aac', 'mp3', 'vorbis', 'opus'}

def _safe_probe_filelike_to_path(fobj) -> str:
    """
    Write uploaded file (possibly InMemoryUploadedFile) to a temp file
    and return its absolute path for ffprobe.
    """
    # اگر آبجکت آپلودی chunk دارد، از آن استفاده کن
    if hasattr(fobj, "chunks"):
        with NamedTemporaryFile(delete=False, suffix=os.path.splitext(getattr(fobj, "name", "") or "upload")[1]) as tmp:
            for chunk in fobj.chunks():
                tmp.write(chunk)
            return tmp.name
    # در غیر این صورت سعی کن فایل را بخوانی
    with NamedTemporaryFile(delete=False) as tmp:
        tmp.write(fobj.read())
        return tmp.name

def validate_audio_file(value):
    """
    Accepts common browser-recorded audio (WebM/Opus) and typical uploads (mp3, m4a, wav, ogg).
    Uses content_type first; falls back to extension; finally verifies via ffprobe.
    """
    # 1) Normalize content_type (remove codecs, lowercase)
    ct = (getattr(value, "content_type", "") or "").split(";", 1)[0].strip().lower()
    name = getattr(value, "name", "") or ""

    # 2) Quick coarse check via your generic map
    kind = validate_file_type(name, ct)

    # Special-case: many browsers set ".webm" as video/webm even for audio-only
    # We treat ".webm" as candidate for audio and let ffprobe be the source of truth.
    _, ext = os.path.splitext(name.lower())
    if not kind and ext == ".webm":
        kind = "audio"  # provisional, verify below

    if kind not in {"audio"}:
        # one more fallback: guess from filename if content_type was empty/misleading
        guessed, _ = mimetypes.guess_type(name)
        guessed = (guessed or "").split(";", 1)[0].strip().lower()
        if validate_file_type(name, guessed) != "audio":
            raise ValidationError("Only audio files are allowed.")

    # 3) Probe with ffmpeg to ensure at least one audio stream exists
    tmp_path = None
    try:
        # Ensure we have a real path for ffprobe
        # If TemporaryUploadedFile -> has temporary_file_path()
        if hasattr(value, "temporary_file_path"):
            tmp_path = value.temporary_file_path()
        else:
            tmp_path = _safe_probe_filelike_to_path(value.file)

        probe = ffmpeg.probe(tmp_path)
        # pick first audio stream
        stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'audio'), None)
        if not stream:
            raise ValidationError("No audio stream found.")

        codec = (stream.get('codec_name') or "").lower()
        if codec and codec not in ALLOWED_AUDIO_CODECS:
            # برای ایمنی حداقلی نگه می‌داریم، ولی opus/aac/mp3/vorbis را مجاز می‌دانیم
            raise ValidationError(f"Unsupported audio codec: {codec}")

        # بیت‌ریت را سخت نمی‌گیریم؛ بسیاری از فایل‌های opus مقدار دقیق ندارند
        # اگر می‌خواهید چک سبک بماند، این بخش را حذف کنید یا فقط اگر بسیار بالا بود رد کنید.
        # bit_rate = int(stream.get('bit_rate', 0) or 0)
        # if bit_rate and bit_rate > 512000:  # e.g. > 512kbps (غیرعادی برای گفتار)
        #     raise ValidationError(f"Audio bitrate {bit_rate} too high.")

    except ValidationError:
        raise
    except Exception as e:
        # در صورت خطای probe، به جای رد کردن مطلق، پیام شفاف بدهید
        raise ValidationError(f"Invalid audio file (probe failed).")
    finally:
        # Clean temp file if we created it
        try:
            if tmp_path and not hasattr(value, "temporary_file_path") and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
