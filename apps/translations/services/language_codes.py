# apps/translations/services/language_codes.py

from __future__ import annotations

import re
from functools import lru_cache
from typing import Optional

from apps.translations.services.supported_languages import get_supported_languages

AWS_LANG_RE = re.compile(r"^(?:[a-zA-Z]{2,4}|[a-zA-Z]{2}-[a-zA-Z]{2})$")

# Whisper sometimes returns names like "english" not "en"
# Full mapping based on supported_languages.py (English names -> codes)
WHISPER_NAME_ALIASES: dict[str, str] = {
    "afrikaans": "af",
    "albanian": "sq",
    "amharic": "am",
    "arabic": "ar",
    "armenian": "hy",
    "azerbaijani": "az",
    "bengali": "bn",
    "bosnian": "bs",
    "bulgarian": "bg",
    "catalan": "ca",
    "chinese (simplified)": "zh",
    "chinese (traditional)": "zh-TW",
    "croatian": "hr",
    "czech": "cs",
    "danish": "da",
    "dari": "fa-AF",
    "dutch": "nl",
    "english": "en",
    "estonian": "et",
    "persian": "fa",
    "filipino / tagalog": "tl",
    "finnish": "fi",
    "french": "fr",
    "french (canada)": "fr-CA",
    "georgian": "ka",
    "german": "de",
    "greek": "el",
    "gujarati": "gu",
    "haitian creole": "ht",
    "hausa": "ha",
    "hebrew": "he",
    "hindi": "hi",
    "hungarian": "hu",
    "icelandic": "is",
    "indonesian": "id",
    "irish": "ga",
    "italian": "it",
    "japanese": "ja",
    "kannada": "kn",
    "kazakh": "kk",
    "korean": "ko",
    "latvian": "lv",
    "lithuanian": "lt",
    "macedonian": "mk",
    "malay": "ms",
    "malayalam": "ml",
    "maltese": "mt",
    "marathi": "mr",
    "mongolian": "mn",
    "norwegian (bokmål)": "no",
    "pashto": "ps",
    "polish": "pl",
    "portuguese (brazil)": "pt",
    "portuguese (portugal)": "pt-PT",
    "punjabi": "pa",
    "romanian": "ro",
    "russian": "ru",
    "serbian": "sr",
    "sinhala": "si",
    "slovak": "sk",
    "slovenian": "sl",
    "somali": "so",
    "spanish": "es",
    "spanish (mexico)": "es-MX",
    "swahili": "sw",
    "swedish": "sv",
    "tamil": "ta",
    "telugu": "te",
    "thai": "th",
    "turkish": "tr",
    "ukrainian": "uk",
    "urdu": "ur",
    "uzbek": "uz",
    "vietnamese": "vi",
    "welsh": "cy",

    # Common extras / colloquial names that appear in real logs
    "farsi": "fa",
}

@lru_cache(maxsize=1)
def _name_to_code_index() -> dict[str, str]:
    """
    Build a reverse index from UI language list:
    - english name -> code
    - native name  -> code
    - label        -> code
    Lowercased for matching.
    """
    idx: dict[str, str] = {}
    for item in get_supported_languages():
        code = item["code"]
        idx[item["english"].strip().lower()] = code
        idx[item["native"].strip().lower()] = code
        idx[item["label"].strip().lower()] = code
    return idx

def normalize_language_code(value: Optional[str]) -> str:
    """
    Normalize language input into a standard code (prefer BCP-47 like 'en', 'fa', 'fr-CA').
    Accepts:
      - 'en', 'en-US'
      - 'english', 'persian', 'فارسی'
      - UI labels like 'English (English)'
    """
    if not value:
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    low = raw.lower()

    # 1) Already a code? (en / en-US / fr / fa-AF ...)
    if AWS_LANG_RE.match(raw):
        return raw  # keep case like fa-AF, fr-CA if user stored it

    # 2) Whisper common names
    if low in WHISPER_NAME_ALIASES:
        return WHISPER_NAME_ALIASES[low]

    # 3) Match from supported languages list (english/native/label)
    idx = _name_to_code_index()
    if low in idx:
        return idx[low]

    # 4) Last-resort: try first 2 letters if they look alphabetic
    # (prevents passing "english" into AWS)
    if low.isalpha() and len(low) >= 2:
        return low[:2]

    return ""
