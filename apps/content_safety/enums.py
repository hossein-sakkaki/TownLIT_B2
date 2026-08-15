# apps/content_safety/enums.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from django.db import models


class SafetyInputType(models.TextChoices):
    TEXT = "text", "Text"
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"


class SafetyDecision(models.TextChoices):
    ALLOW = "allow", "Allow"
    REVIEW = "review", "Review"
    BLOCK = "block", "Block"


class SafetyRiskLevel(models.TextChoices):
    LOW = "low", "Low"
    MEDIUM = "medium", "Medium"
    HIGH = "high", "High"
    CRITICAL = "critical", "Critical"


class SafetyContext(models.TextChoices):
    GENERIC = "generic", "Generic"

    MOMENT_CAPTION = (
        "moment_caption",
        "Moment Caption",
    )

    PRAYER = (
        "prayer",
        "Prayer",
    )

    TESTIMONY = (
        "testimony",
        "Testimony",
    )

    COMMENT = (
        "comment",
        "Comment",
    )

    REPLY = (
        "reply",
        "Reply",
    )

    JOURNEY_TEXT = (
        "journey_text",
        "Journey Text",
    )

    PROFILE_TEXT = (
        "profile_text",
        "Profile Text",
    )

    GROUP_TEXT = (
        "group_text",
        "Group Text",
    )

    GROUP_MESSAGE = (
        "group_message",
        "Group Message",
    )

    MOMENT_MEDIA = (
        "moment_media",
        "Moment Media",
    )

    PRAYER_MEDIA = (
        "prayer_media",
        "Prayer Media",
    )

    TESTIMONY_MEDIA = (
        "testimony_media",
        "Testimony Media",
    )

    JOURNEY_MEDIA = (
        "journey_media",
        "Journey Media",
    )

    PROFILE_MEDIA = (
        "profile_media",
        "Profile Media",
    )

    GROUP_MESSAGE_MEDIA = (
        "group_message_media",
        "Group Message Media",
    )

    MOMENT_IMAGE = (
        "moment_image",
        "Moment Image",
    )

    # PROFILE_IMAGE = (
    #     "profile_image",
    #     "Profile Image",
    # )

    # AVATAR_IMAGE = (
    #     "avatar_image",
    #     "Avatar Image",
    # )
    
    TESTIMONY_IMAGE = (
        "testimony_image",
        "Testimony Image",
    )

    JOURNEY_IMAGE = (
        "journey_image",
        "Journey Image",
    )

    GROUP_IMAGE = (
        "group_image",
        "Group Image",
    )
    
class SafetyReason(models.TextChoices):
    SAFE = "safe", "Safe"

    PROFANITY = (
        "profanity",
        "Profanity",
    )

    ABUSIVE_LANGUAGE = (
        "abusive_language",
        "Abusive Language",
    )

    PERSONAL_ATTACK = (
        "personal_attack",
        "Personal Attack",
    )

    BULLYING = (
        "bullying",
        "Bullying",
    )

    HARASSMENT = (
        "harassment",
        "Harassment",
    )

    HARASSMENT_THREATENING = (
        "harassment_threatening",
        "Threatening Harassment",
    )

    HATE = (
        "hate",
        "Hate",
    )

    HATE_THREATENING = (
        "hate_threatening",
        "Threatening Hate",
    )

    SEXUAL = (
        "sexual",
        "Sexual Content",
    )

    SEXUAL_EXPLICIT = (
        "sexual_explicit",
        "Explicit Sexual Content",
    )

    SEXUAL_SOLICITATION = (
        "sexual_solicitation",
        "Sexual Solicitation",
    )

    SEXUAL_MINORS = (
        "sexual_minors",
        "Sexual Content Involving Minors",
    )

    SELF_HARM = (
        "self_harm",
        "Self Harm",
    )

    SELF_HARM_INTENT = (
        "self_harm_intent",
        "Self Harm Intent",
    )

    SELF_HARM_INSTRUCTIONS = (
        "self_harm_instructions",
        "Self Harm Instructions",
    )

    VIOLENCE = (
        "violence",
        "Violence",
    )

    VIOLENCE_GRAPHIC = (
        "violence_graphic",
        "Graphic Violence",
    )

    ILLICIT = (
        "illicit",
        "Illicit Instructions",
    )

    ILLICIT_VIOLENT = (
        "illicit_violent",
        "Violent Illicit Instructions",
    )

    SPAM = (
        "spam",
        "Spam",
    )

    SCAM = (
        "scam",
        "Scam",
    )

    PROVIDER_FLAGGED = (
        "provider_flagged",
        "Provider Flagged",
    )

    LOCAL_SIGNAL = (
        "local_signal",
        "Local Safety Signal",
    )

    ADJUDICATION_REQUIRED = (
        "adjudication_required",
        "Adjudication Required",
    )

    PROVIDER_UNAVAILABLE = (
        "provider_unavailable",
        "Provider Unavailable",
    )