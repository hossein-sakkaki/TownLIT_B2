# apps/content_safety/services/local_signals.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from __future__ import annotations

import re

from apps.content_safety.services.types import (
    LocalSafetySignals,
)


_REPEATED_CHARACTER_RE = re.compile(
    r"(.)\1{11,}",
    flags=re.UNICODE,
)

_REPEATED_TOKEN_RE = re.compile(
    r"\b(\S+)(?:\s+\1){5,}\b",
    flags=re.IGNORECASE | re.UNICODE,
)

_EXCESSIVE_URL_RE = re.compile(
    r"(?:https?://|www\.)",
    flags=re.IGNORECASE,
)

_SEXUAL_SOLICITATION_PATTERNS = (
    re.compile(
        r"\bsend\s+(?:me\s+)?(?:nudes?|naked\s+(?:pics?|photos?))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bshow\s+(?:me\s+)?(?:your\s+)?(?:nudes?|naked\s+body)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bsext(?:ing)?\b",
        re.IGNORECASE,
    ),
)

_ENGLISH_SEVERE_PROFANITY_PATTERNS = (
    re.compile(
        r"\bf+u+c+k+(?:er|ing|ed|s)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bm+o+t+h+e+r+f+u+c+k+\w*\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bc+u+n+t+\w*\b",
        re.IGNORECASE,
    ),
)

_PERSIAN_SEVERE_PROFANITY_PATTERNS = (
    re.compile(
        r"(?:کیر|کون|کسکش|جنده|حرومزاده|حرامزاده)",
        re.IGNORECASE,
    ),
)

_ARABIC_SEVERE_PROFANITY_PATTERNS = (
    re.compile(
        r"(?:شرموط|قحبة|كس\s*أمك|ابن\s*القحبة)",
        re.IGNORECASE,
    ),
)


def _matches_any(
    *,
    text: str,
    patterns: tuple[re.Pattern, ...],
) -> bool:
    return any(
        pattern.search(
            text
        )
        is not None
        for pattern in patterns
    )


def _has_spam_signal(
    text: str,
) -> bool:
    if _REPEATED_CHARACTER_RE.search(
        text
    ):
        return True

    if _REPEATED_TOKEN_RE.search(
        text
    ):
        return True

    url_count = len(
        _EXCESSIVE_URL_RE.findall(
            text
        )
    )

    return url_count >= 5


def inspect_local_text_signals(
    *,
    text: str,
) -> LocalSafetySignals:
    """
    Detect cheap high-confidence local signals.
    """

    profanity = (
        _matches_any(
            text=text,
            patterns=_ENGLISH_SEVERE_PROFANITY_PATTERNS,
        )
        or _matches_any(
            text=text,
            patterns=_PERSIAN_SEVERE_PROFANITY_PATTERNS,
        )
        or _matches_any(
            text=text,
            patterns=_ARABIC_SEVERE_PROFANITY_PATTERNS,
        )
    )

    sexual_solicitation = _matches_any(
        text=text,
        patterns=_SEXUAL_SOLICITATION_PATTERNS,
    )

    spam = _has_spam_signal(
        text
    )

    reasons: list[str] = []

    if profanity:
        reasons.append(
            "profanity"
        )

    if sexual_solicitation:
        reasons.append(
            "sexual_solicitation"
        )

    if spam:
        reasons.append(
            "spam"
        )

    return LocalSafetySignals(
        suspicious=bool(
            reasons
        ),
        profanity=profanity,
        sexual_solicitation=sexual_solicitation,
        spam=spam,
        reasons=tuple(
            reasons
        ),
    )