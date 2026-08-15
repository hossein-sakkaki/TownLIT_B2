# apps/content_safety/services/image_rules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-14.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

import re

from apps.content_safety.enums import (
    SafetyContext,
    SafetyReason,
)


_ALLOWED_REASON_CODES = {
    SafetyReason.SAFE,
    SafetyReason.HARASSMENT,
    SafetyReason.HARASSMENT_THREATENING,
    SafetyReason.HATE,
    SafetyReason.HATE_THREATENING,
    SafetyReason.SEXUAL,
    SafetyReason.SEXUAL_EXPLICIT,
    SafetyReason.SEXUAL_SOLICITATION,
    SafetyReason.SEXUAL_MINORS,
    SafetyReason.SELF_HARM,
    SafetyReason.SELF_HARM_INTENT,
    SafetyReason.SELF_HARM_INSTRUCTIONS,
    SafetyReason.VIOLENCE,
    SafetyReason.VIOLENCE_GRAPHIC,
    SafetyReason.PROVIDER_FLAGGED,
    SafetyReason.ADJUDICATION_REQUIRED,
}


_REASON_ALIASES = {
    "explicit_sexual_content": (
        SafetyReason.SEXUAL_EXPLICIT
    ),
    "explicit_sexual": (
        SafetyReason.SEXUAL_EXPLICIT
    ),
    "pornography": (
        SafetyReason.SEXUAL_EXPLICIT
    ),
    "pornographic": (
        SafetyReason.SEXUAL_EXPLICIT
    ),
    "sexualized_nudity": (
        SafetyReason.SEXUAL_EXPLICIT
    ),
    "nudity": (
        SafetyReason.SEXUAL
    ),
    "child_sexual_content": (
        SafetyReason.SEXUAL_MINORS
    ),
    "sexual_content_involving_minors": (
        SafetyReason.SEXUAL_MINORS
    ),
    "minor_sexualization": (
        SafetyReason.SEXUAL_MINORS
    ),
    "graphic_violence": (
        SafetyReason.VIOLENCE_GRAPHIC
    ),
    "graphic_gore": (
        SafetyReason.VIOLENCE_GRAPHIC
    ),
    "violent_content": (
        SafetyReason.VIOLENCE
    ),
    "hate_speech": (
        SafetyReason.HATE
    ),
    "hate_symbol": (
        SafetyReason.HATE
    ),
    "hate_symbols": (
        SafetyReason.HATE
    ),
    "self_harm_content": (
        SafetyReason.SELF_HARM
    ),
    "self_harm_instruction": (
        SafetyReason.SELF_HARM_INSTRUCTIONS
    ),
}


def context_value(
    value,
) -> str:
    raw_value = getattr(
        value,
        "value",
        value,
    )

    return str(
        raw_value
        or ""
    ).strip().lower()


def normalize_image_reason_code(
    value: str,
) -> str:
    reason = str(
        value
        or ""
    ).strip().lower()

    reason = re.sub(
        r"[^a-z0-9]+",
        "_",
        reason,
    ).strip(
        "_"
    )

    if reason in {
        str(item)
        for item in _ALLOWED_REASON_CODES
    }:
        return reason

    alias = _REASON_ALIASES.get(
        reason
    )

    if alias:
        return str(
            alias
        )

    return str(
        SafetyReason.PROVIDER_FLAGGED
    )


def image_context_guidance(
    context: str,
) -> str:
    normalized = context_value(
        context
    )

    if normalized == context_value(
        SafetyContext.MOMENT_MEDIA
    ):
        return (
            "MOMENT-MEDIA-SPECIFIC RULES:\n"
            "- This image is intended for a public or socially visible Moment.\n"
            "- Allow normal daily-life photography, portraits, food, travel, "
            "fitness, worship, church activity, art, nature, and family content.\n"
            "- Do not block legitimate documentary, historical, medical, "
            "educational, recovery, or awareness imagery merely because a "
            "sensitive subject appears.\n"
            "- Block pornography, sexualized nudity, sexual exploitation, "
            "sexualization of minors, gratuitous graphic gore, hate promotion, "
            "or imagery materially encouraging serious harm.\n"
        )

    if normalized == context_value(
        SafetyContext.PRAYER_MEDIA
    ):
        return (
            "PRAYER-MEDIA-SPECIFIC RULES:\n"
            "- Images may document illness, injury, grief, crisis, recovery, "
            "hospital treatment, or circumstances for which prayer is requested.\n"
            "- Allow non-gratuitous medical, recovery, scar, injury, or pastoral "
            "imagery when its purpose is legitimate.\n"
            "- Do not confuse evidence of suffering with encouragement of harm.\n"
            "- Block pornography, sexual exploitation, sexualization of minors, "
            "gratuitous gore intended primarily to shock, or imagery that "
            "materially promotes serious harm.\n"
        )

    if normalized == context_value(
        SafetyContext.TESTIMONY_MEDIA
    ):
        return (
            "TESTIMONY-MEDIA-SPECIFIC RULES:\n"
            "- Images may accompany personal stories of trauma, abuse, recovery, "
            "addiction, illness, persecution, injury, grief, or healing.\n"
            "- Allow non-gratuitous documentary evidence such as scars, medical "
            "treatment, recovery imagery, or historical material when legitimate.\n"
            "- Survivor material must not be treated as endorsement of the abuse "
            "being described.\n"
            "- Block pornography, sexual exploitation, sexualization of minors, "
            "gratuitous graphic gore, or imagery promoting serious violence or "
            "self-harm.\n"
        )

    if normalized == context_value(
        SafetyContext.JOURNEY_MEDIA
    ):
        return (
            "JOURNEY-MEDIA-SPECIFIC RULES:\n"
            "- Journey is a visual social-story format.\n"
            "- Allow normal selfies, family images, worship, travel, art, food, "
            "fitness, nature, ministry, and everyday-life photography.\n"
            "- Historical, artistic, biblical, documentary, or educational "
            "violence should be judged by actual purpose and context.\n"
            "- Block pornography, sexualized nudity, exploitation, sexualization "
            "of minors, gratuitous graphic gore, hate promotion, or imagery "
            "materially encouraging serious harm.\n"
        )

    if normalized == context_value(
        SafetyContext.PROFILE_MEDIA
    ):
        return (
            "PROFILE-MEDIA-SPECIFIC RULES:\n"
            "- This image may represent a user's public identity or profile.\n"
            "- Allow ordinary portraits, professional photos, ministry images, "
            "faith-related imagery, and normal personal photography.\n"
            "- Apply a somewhat stricter public-profile standard to gratuitous "
            "sexual or graphic imagery.\n"
            "- Block pornography, sexualized nudity, sexual exploitation, "
            "sexualization of minors, graphic gore, hate promotion, or imagery "
            "materially encouraging serious harm.\n"
        )

    if normalized == context_value(
        SafetyContext.GROUP_MESSAGE_MEDIA
    ):
        return (
            "GROUP-MESSAGE-MEDIA-SPECIFIC RULES:\n"
            "- This image is shared inside a multi-user group conversation.\n"
            "- Allow ordinary conversation images, memes, worship material, "
            "faith discussion, education, pastoral support, recovery material, "
            "and legitimate documentary or medical imagery.\n"
            "- Do not over-moderate survivor-support or sensitive discussion.\n"
            "- Block pornography, sexual exploitation, sexualization of minors, "
            "gratuitous sexualized imagery, graphic gore intended primarily to "
            "shock, hate promotion, or imagery materially encouraging serious harm.\n"
        )

    return (
        "GENERAL IMAGE RULES:\n"
        "- Allow normal social photography, portraits, family content, worship, "
        "art, travel, food, fitness, education, and everyday life.\n"
        "- Allow legitimate medical, historical, documentary, pastoral, "
        "recovery, biblical, and educational imagery when it is not exploitative "
        "or gratuitous.\n"
        "- Block pornography, sexualized nudity, sexual exploitation, "
        "sexualization of minors, gratuitous graphic gore, hate promotion, "
        "and imagery materially encouraging serious harm.\n"
    )