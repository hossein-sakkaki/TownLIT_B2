# validators/groupNames/group_name_validator.py

import re
from django.core.exceptions import ValidationError


MIN_GROUP_NAME_LENGTH = 3
MAX_GROUP_NAME_LENGTH = 60


PROFANE_WORDS = [
    # Vulgar / obscene language
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt", "slut", "dick", "piss",
    "whore", "retard", "faggot", "nigger", "nigga", "twat", "wank", "bugger", "cock",
    "dildo", "damn",

    # Racial / discriminatory / extremist terms
    "nazi", "hitler", "kkk", "klan", "whitepower", "racist", "supremacy",

    # Satanic / demonic / anti-faith references
    "satan", "lucifer", "demon", "devil", "hell", "satanic", "antichrist", "666",
    "hellfire", "beelzebub",

    # Threats / violence / criminal language
    "kill", "murder", "terrorist", "suicide", "rape", "abuse", "massacre", "bloodbath",

    # Drugs / substance abuse
    "cocaine", "heroin", "meth", "weed", "marijuana", "ecstasy", "lsd", "crack",
    "dope", "stoned",
]


SYSTEM_WORDS = [
    "official",
    "superuser",
    "support",
    "dev",
    "developer",
    "townlit",
    "admin",
    "administrator",
    "moderator",
    "staff",
    "security",
    "verified",
    "system",
    "team",
    "helpdesk",
    "service",
]


SACRED_WORDS = [
    "god",
    "jesus",
    "christ",
    "yahweh",
    "holyspirit",
    "holy spirit",
]


LINK_PATTERNS = [
    "http://",
    "https://",
    "www.",
    ".com",
    ".net",
    ".org",
    ".io",
    ".app",
    ".ca",
    ".co",
]


def normalize_group_name(value: str | None) -> str:
    """
    Normalize user-facing group names before validation/storage.
    Keeps display text natural while removing repeated whitespace.
    """
    if value is None:
        return ""

    normalized = str(value).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _compact_name(value: str) -> str:
    """
    Compact version catches deceptive forms like:
    T o w n L I T, holy-spirit, admin_team.
    """
    return re.sub(r"[^a-zA-Z0-9]+", "", value.lower())


def validate_group_name(value: str | None) -> str:
    """
    Validate and return normalized group name.

    Raises django.core.exceptions.ValidationError when invalid.
    This function is safe to reuse in DRF serializers, services, and models.
    """
    name = normalize_group_name(value)
    lower_name = name.lower()
    compact_name = _compact_name(name)

    if not lower_name:
        raise ValidationError("Group name is required.", code="required")

    if len(lower_name) < MIN_GROUP_NAME_LENGTH:
        raise ValidationError(
            f"Group name must be at least {MIN_GROUP_NAME_LENGTH} characters.",
            code="too_short",
        )

    if len(lower_name) > MAX_GROUP_NAME_LENGTH:
        raise ValidationError(
            f"Group name must be {MAX_GROUP_NAME_LENGTH} characters or less.",
            code="too_long",
        )

    if re.fullmatch(r"[^a-zA-Z0-9]+", lower_name):
        raise ValidationError(
            "Group name must contain at least one letter or number.",
            code="no_letter_or_number",
        )

    if any(pattern in lower_name for pattern in LINK_PATTERNS):
        raise ValidationError(
            "Group name cannot contain website or link references.",
            code="contains_link",
        )

    if any(word in lower_name for word in PROFANE_WORDS):
        raise ValidationError(
            "Group name contains inappropriate language.",
            code="inappropriate_language",
        )

    if any(word in compact_name or word in lower_name for word in SYSTEM_WORDS):
        raise ValidationError(
            "Group name cannot reference TownLIT system, support, admin, or official identities.",
            code="reserved_system_identity",
        )

    sacred_compact_words = [_compact_name(word) for word in SACRED_WORDS]
    if lower_name in SACRED_WORDS or compact_name in sacred_compact_words:
        raise ValidationError(
            f'Using sacred names like "{name}" alone is not allowed. Please use it as part of a meaningful phrase.',
            code="sacred_name_alone",
        )

    return name