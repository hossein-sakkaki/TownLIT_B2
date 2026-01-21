from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Dict


@dataclass(frozen=True)
class LanguageOption:
    code: str
    native: str        # Language name in its own language
    english: str       # English name (fallback / secondary)


@lru_cache(maxsize=1)
def get_supported_languages() -> List[Dict[str, str]]:
    """
    Returns a curated list of supported languages.
    Each language includes native + English labels for UI flexibility.
    """

    langs = [
        LanguageOption("af", "Afrikaans", "Afrikaans"),
        LanguageOption("sq", "Shqip", "Albanian"),
        LanguageOption("am", "አማርኛ", "Amharic"),
        LanguageOption("ar", "العربية", "Arabic"),
        LanguageOption("hy", "Հայերեն", "Armenian"),
        LanguageOption("az", "Azərbaycan dili", "Azerbaijani"),
        LanguageOption("bn", "বাংলা", "Bengali"),
        LanguageOption("bs", "Bosanski", "Bosnian"),
        LanguageOption("bg", "Български", "Bulgarian"),
        LanguageOption("ca", "Català", "Catalan"),
        LanguageOption("zh", "中文（简体）", "Chinese (Simplified)"),
        LanguageOption("zh-TW", "中文（繁體）", "Chinese (Traditional)"),
        LanguageOption("hr", "Hrvatski", "Croatian"),
        LanguageOption("cs", "Čeština", "Czech"),
        LanguageOption("da", "Dansk", "Danish"),
        LanguageOption("fa-AF", "دری", "Dari"),
        LanguageOption("nl", "Nederlands", "Dutch"),
        LanguageOption("en", "English", "English"),
        LanguageOption("et", "Eesti", "Estonian"),
        LanguageOption("fa", "فارسی", "Persian"),
        LanguageOption("tl", "Filipino", "Filipino / Tagalog"),
        LanguageOption("fi", "Suomi", "Finnish"),
        LanguageOption("fr", "Français", "French"),
        LanguageOption("fr-CA", "Français (Canada)", "French (Canada)"),
        LanguageOption("ka", "ქართული", "Georgian"),
        LanguageOption("de", "Deutsch", "German"),
        LanguageOption("el", "Ελληνικά", "Greek"),
        LanguageOption("gu", "ગુજરાતી", "Gujarati"),
        LanguageOption("ht", "Kreyòl Ayisyen", "Haitian Creole"),
        LanguageOption("ha", "Hausa", "Hausa"),
        LanguageOption("he", "עברית", "Hebrew"),
        LanguageOption("hi", "हिन्दी", "Hindi"),
        LanguageOption("hu", "Magyar", "Hungarian"),
        LanguageOption("is", "Íslenska", "Icelandic"),
        LanguageOption("id", "Bahasa Indonesia", "Indonesian"),
        LanguageOption("ga", "Gaeilge", "Irish"),
        LanguageOption("it", "Italiano", "Italian"),
        LanguageOption("ja", "日本語", "Japanese"),
        LanguageOption("kn", "ಕನ್ನಡ", "Kannada"),
        LanguageOption("kk", "Қазақ тілі", "Kazakh"),
        LanguageOption("ko", "한국어", "Korean"),
        LanguageOption("lv", "Latviešu", "Latvian"),
        LanguageOption("lt", "Lietuvių", "Lithuanian"),
        LanguageOption("mk", "Македонски", "Macedonian"),
        LanguageOption("ms", "Bahasa Melayu", "Malay"),
        LanguageOption("ml", "മലയാളം", "Malayalam"),
        LanguageOption("mt", "Malti", "Maltese"),
        LanguageOption("mr", "मराठी", "Marathi"),
        LanguageOption("mn", "Монгол", "Mongolian"),
        LanguageOption("no", "Norsk (Bokmål)", "Norwegian (Bokmål)"),
        LanguageOption("ps", "پښتو", "Pashto"),
        LanguageOption("pl", "Polski", "Polish"),
        LanguageOption("pt", "Português (Brasil)", "Portuguese (Brazil)"),
        LanguageOption("pt-PT", "Português (Portugal)", "Portuguese (Portugal)"),
        LanguageOption("pa", "ਪੰਜਾਬੀ", "Punjabi"),
        LanguageOption("ro", "Română", "Romanian"),
        LanguageOption("ru", "Русский", "Russian"),
        LanguageOption("sr", "Српски", "Serbian"),
        LanguageOption("si", "සිංහල", "Sinhala"),
        LanguageOption("sk", "Slovenčina", "Slovak"),
        LanguageOption("sl", "Slovenščina", "Slovenian"),
        LanguageOption("so", "Soomaaliga", "Somali"),
        LanguageOption("es", "Español", "Spanish"),
        LanguageOption("es-MX", "Español (México)", "Spanish (Mexico)"),
        LanguageOption("sw", "Kiswahili", "Swahili"),
        LanguageOption("sv", "Svenska", "Swedish"),
        LanguageOption("ta", "தமிழ்", "Tamil"),
        LanguageOption("te", "తెలుగు", "Telugu"),
        LanguageOption("th", "ไทย", "Thai"),
        LanguageOption("tr", "Türkçe", "Turkish"),
        LanguageOption("uk", "Українська", "Ukrainian"),
        LanguageOption("ur", "اردو", "Urdu"),
        LanguageOption("uz", "O‘zbek", "Uzbek"),
        LanguageOption("vi", "Tiếng Việt", "Vietnamese"),
        LanguageOption("cy", "Cymraeg", "Welsh"),
    ]

    return [
        {
            "code": l.code,
            "native": l.native,
            "english": l.english,
            # Recommended default UI label
            "label": f"{l.english} ({l.native})",
        }
        for l in langs
    ]
