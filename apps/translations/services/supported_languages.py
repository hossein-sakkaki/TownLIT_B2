# apps/translations/services/supported_languages.py
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Dict

# Keep this as a single source of truth (server-side)
# AWS Translate language list can change; we expose it via API.
# For now, implement a curated list OR wire to boto3 "list_languages" if you prefer.

@dataclass(frozen=True)
class LanguageOption:
    code: str
    label: str


@lru_cache(maxsize=1)
def get_supported_languages() -> List[Dict[str, str]]:
    """
    Returns list of languages supported by our translation provider.
    Cached in-process to avoid repeated work.
    """
    # ✅ Option 1 (recommended now): server-managed list (stable + explicit)
    # Later you can swap to boto3 list_languages() if you want.
    langs = [
        LanguageOption("af", "Afrikaans"),
        LanguageOption("sq", "Albanian"),
        LanguageOption("am", "Amharic"),
        LanguageOption("ar", "Arabic"),
        LanguageOption("hy", "Armenian"),
        LanguageOption("az", "Azerbaijani"),
        LanguageOption("bn", "Bengali"),
        LanguageOption("bs", "Bosnian"),
        LanguageOption("bg", "Bulgarian"),
        LanguageOption("ca", "Catalan"),
        LanguageOption("zh", "Chinese (Simplified)"),
        LanguageOption("zh-TW", "Chinese (Traditional)"),
        LanguageOption("hr", "Croatian"),
        LanguageOption("cs", "Czech"),
        LanguageOption("da", "Danish"),
        LanguageOption("fa-AF", "Dari"),
        LanguageOption("nl", "Dutch"),
        LanguageOption("en", "English"),
        LanguageOption("et", "Estonian"),
        LanguageOption("fa", "Farsi (Persian)"),
        LanguageOption("tl", "Filipino, Tagalog"),
        LanguageOption("fi", "Finnish"),
        LanguageOption("fr", "French"),
        LanguageOption("fr-CA", "French (Canada)"),
        LanguageOption("ka", "Georgian"),
        LanguageOption("de", "German"),
        LanguageOption("el", "Greek"),
        LanguageOption("gu", "Gujarati"),
        LanguageOption("ht", "Haitian Creole"),
        LanguageOption("ha", "Hausa"),
        LanguageOption("he", "Hebrew"),
        LanguageOption("hi", "Hindi"),
        LanguageOption("hu", "Hungarian"),
        LanguageOption("is", "Icelandic"),
        LanguageOption("id", "Indonesian"),
        LanguageOption("ga", "Irish"),
        LanguageOption("it", "Italian"),
        LanguageOption("ja", "Japanese"),
        LanguageOption("kn", "Kannada"),
        LanguageOption("kk", "Kazakh"),
        LanguageOption("ko", "Korean"),
        LanguageOption("lv", "Latvian"),
        LanguageOption("lt", "Lithuanian"),
        LanguageOption("mk", "Macedonian"),
        LanguageOption("ms", "Malay"),
        LanguageOption("ml", "Malayalam"),
        LanguageOption("mt", "Maltese"),
        LanguageOption("mr", "Marathi"),
        LanguageOption("mn", "Mongolian"),
        LanguageOption("no", "Norwegian (Bokmål)"),
        LanguageOption("ps", "Pashto"),
        LanguageOption("pl", "Polish"),
        LanguageOption("pt", "Portuguese (Brazil)"),
        LanguageOption("pt-PT", "Portuguese (Portugal)"),
        LanguageOption("pa", "Punjabi"),
        LanguageOption("ro", "Romanian"),
        LanguageOption("ru", "Russian"),
        LanguageOption("sr", "Serbian"),
        LanguageOption("si", "Sinhala"),
        LanguageOption("sk", "Slovak"),
        LanguageOption("sl", "Slovenian"),
        LanguageOption("so", "Somali"),
        LanguageOption("es", "Spanish"),
        LanguageOption("es-MX", "Spanish (Mexico)"),
        LanguageOption("sw", "Swahili"),
        LanguageOption("sv", "Swedish"),
        LanguageOption("ta", "Tamil"),
        LanguageOption("te", "Telugu"),
        LanguageOption("th", "Thai"),
        LanguageOption("tr", "Turkish"),
        LanguageOption("uk", "Ukrainian"),
        LanguageOption("ur", "Urdu"),
        LanguageOption("uz", "Uzbek"),
        LanguageOption("vi", "Vietnamese"),
        LanguageOption("cy", "Welsh"),
    ]


    return [{"code": l.code, "label": l.label} for l in langs]
