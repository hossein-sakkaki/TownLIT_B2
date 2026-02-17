# apps/subtitles/services/audio_source.py

from django.core.files.storage import default_storage
import tempfile

def fetch_audio_from_storage(file_field) -> str:
    suffix = "." + (file_field.name.split(".")[-1] or "wav")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)

    with default_storage.open(file_field.name, "rb") as rf:
        while True:
            chunk = rf.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)

    tmp.flush()
    tmp.close()
    return tmp.name
