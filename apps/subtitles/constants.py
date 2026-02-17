# apps/subtitles/constants.py

"""
Canonical list of pre-generated subtitle languages for TownLIT.

Policy:
- Generated automatically after transcript is ready
- Includes only high-impact, global languages
- All others are on-demand + cached
"""

# Pre-generated subtitle languages (keep as-is) ------------------------------
SUBTITLES_PREGENERATED_LANGUAGES: list[str] = [
    "en",
    "es",
    "fr",
    "fr-CA",
    "ar",
    "fa",
    "fa-AF",
    "tr",
    "de",
    "pt-BR",
    "ru",
    "ur",
    "hi",
    "id",
    "sw",
    "zh",
    "zh-TW",
    "ko",
    "tl",
]


# ------------------------------------------------------------------
# Voice languages (TTS)
# ------------------------------------------------------------------
# Gate by canonical language (base code), e.g.:
#   fr-CA -> fr, fa-AF -> fa, zh-TW -> zh
VOICE_ENABLED_LANGUAGES = [
    "en",  # English
    "fr",  # French
    "es",  # Spanish
    "tr",  # Turkish
    "ar",  # Arabic
    "fa",  # Persian
    "ko",  # Korean
    "zh",  # Chinese (zh / zh-TW)
    "hi",  # Hindi
]



# ------------------------------------------------------------------
# Fallbacks
# ------------------------------------------------------------------
DEFAULT_SAFE_VOICE = "nova"
ENGLISH_FALLBACK_VOICE = "marin"


# ------------------------------------------------------------------
# Default safe voices per language (gender-agnostic)
# Used when gender is unknown or not mapped
# ------------------------------------------------------------------
DEFAULT_VOICE_BY_LANGUAGE = {
    "en": "nova",
    "fr": "marin",
    "es": "ballad",
    "tr": "nova",      # neutral, safe
    "ar": "onyx",
    "fa": "nova",      # fallback if gender unknown
    "ko": "echo",
    "zh": "coral",
    "hi": "nova",
}


# ------------------------------------------------------------------
# Gender-aware defaults (profile-driven)
# Applied ONLY when gender is known
# ------------------------------------------------------------------
DEFAULT_VOICE_BY_LANGUAGE_GENDER = {
    # English
    "en": {
        "male": "onyx",
        "female": "nova",
    },

    # Arabic
    "ar": {
        "male": "onyx",
        "female": "shimmer",   # softer female tone
    },

    # Persian
    "fa": {
        "male": "onyx",
        "female": "shimmer",   # very good fit for fa female
    },

    # French
    "fr": {
        "male": "marin",
        "female": "marin",     # stable, neutral
    },

    # Spanish
    "es": {
        "male": "ballad",
        "female": "ballad",
    },

    # Turkish
    "tr": {
        "male": "nova",
        "female": "nova",
    },

    # Korean
    "ko": {
        "male": "echo",
        "female": "echo",
    },

    # Chinese (zh / zh-TW)
    "zh": {
        "male": "coral",
        "female": "coral",
    },

    # Hindi
    "hi": {
        "male": "nova",
        "female": "nova",
    },
}


# ------------------------------------------------------------------
# OpenAI TTS voices allowed by the API
# ------------------------------------------------------------------
OPENAI_TTS_ALLOWED_VOICES: set[str] = {
    "alloy",
    "echo",
    "fable",
    "onyx",
    "nova",
    "shimmer",
    "coral",
    "verse",
    "ballad",
    "ash",
    "sage",
    "marin",
    "cedar",
}
