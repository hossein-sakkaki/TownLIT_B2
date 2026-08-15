# apps/content_safety/services/policy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from apps.content_safety.enums import (
    SafetyContext,
    SafetyDecision,
    SafetyReason,
    SafetyRiskLevel,
)
from apps.content_safety.services.types import (
    LocalSafetySignals,
    ProviderModerationResult,
    SafetyPolicyResult,
)


_CATEGORY_REASON_MAP = {
    "harassment": (
        SafetyReason.HARASSMENT
    ),
    "harassment/threatening": (
        SafetyReason.HARASSMENT_THREATENING
    ),
    "hate": (
        SafetyReason.HATE
    ),
    "hate/threatening": (
        SafetyReason.HATE_THREATENING
    ),
    "illicit": (
        SafetyReason.ILLICIT
    ),
    "illicit/violent": (
        SafetyReason.ILLICIT_VIOLENT
    ),
    "self-harm": (
        SafetyReason.SELF_HARM
    ),
    "self-harm/intent": (
        SafetyReason.SELF_HARM_INTENT
    ),
    "self-harm/instructions": (
        SafetyReason.SELF_HARM_INSTRUCTIONS
    ),
    "sexual": (
        SafetyReason.SEXUAL
    ),
    "sexual/minors": (
        SafetyReason.SEXUAL_MINORS
    ),
    "violence": (
        SafetyReason.VIOLENCE
    ),
    "violence/graphic": (
        SafetyReason.VIOLENCE_GRAPHIC
    ),
}


_IMMEDIATE_BLOCK_CATEGORIES = {
    "harassment/threatening",
    "hate/threatening",
    "illicit/violent",
    "self-harm/instructions",
    "sexual/minors",
}


_CONTEXT_SENSITIVE_CATEGORIES = {
    "harassment",
    "hate",
    "illicit",
    "self-harm",
    "self-harm/intent",
    "sexual",
    "violence",
    "violence/graphic",
}


_IMAGE_HIGH_RISK_CATEGORIES = {
    "sexual",
    "self-harm/instructions",
    "violence/graphic",
}


_IMAGE_CONTEXTUAL_CATEGORIES = {
    "sexual",
    "self-harm",
    "self-harm/intent",
    "self-harm/instructions",
    "violence",
    "violence/graphic",
}


def _context_value(
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


def _is_testimony_context(
    context,
) -> bool:
    return (
        _context_value(context)
        == _context_value(
            SafetyContext.TESTIMONY
        )
    )


def active_moderation_categories(
    moderation: ProviderModerationResult,
) -> list[str]:
    return [
        category
        for category, active in (
            moderation.categories.items()
        )
        if active
    ]


def active_moderation_categories_for_input(
    moderation: ProviderModerationResult,
    *,
    input_type: str,
) -> list[str]:
    """
    Return active categories that actually apply to one input modality.

    Unknown/missing provider modality metadata is handled conservatively.
    """

    normalized_input_type = str(
        input_type
        or ""
    ).strip().lower()

    active = active_moderation_categories(
        moderation
    )

    resolved: list[str] = []

    for category in active:
        if category not in moderation.applied_input_types:
            resolved.append(
                category
            )
            continue

        applied_types = {
            str(item)
            .strip()
            .lower()
            for item in (
                moderation.applied_input_types.get(
                    category
                )
                or []
            )
            if str(
                item
            ).strip()
        }

        if normalized_input_type in applied_types:
            resolved.append(
                category
            )

    return resolved


def _reason_for_category(
    category: str,
) -> str:
    return str(
        _CATEGORY_REASON_MAP.get(
            category,
            SafetyReason.PROVIDER_FLAGGED,
        )
    )


def evaluate_text_policy(
    *,
    moderation: ProviderModerationResult,
    local_signals: LocalSafetySignals,
    force_contextual_review: bool = False,
    context: str = SafetyContext.GENERIC,
) -> SafetyPolicyResult:
    """
    Convert text safety signals into TownLIT policy.
    """

    active = active_moderation_categories(
        moderation
    )

    testimony_context = _is_testimony_context(
        context
    )

    for category in active:
        if category not in _IMMEDIATE_BLOCK_CATEGORIES:
            continue

        if testimony_context:
            return SafetyPolicyResult(
                decision=SafetyDecision.REVIEW,
                risk_level=SafetyRiskLevel.HIGH,
                reason_code=_reason_for_category(
                    category
                ),
                requires_adjudication=True,
            )

        return SafetyPolicyResult(
            decision=SafetyDecision.BLOCK,
            risk_level=SafetyRiskLevel.CRITICAL,
            reason_code=_reason_for_category(
                category
            ),
            requires_adjudication=False,
        )

    if local_signals.sexual_solicitation:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.HIGH,
            reason_code=SafetyReason.SEXUAL_SOLICITATION,
            requires_adjudication=True,
        )

    if local_signals.profanity:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.MEDIUM,
            reason_code=SafetyReason.PROFANITY,
            requires_adjudication=True,
        )

    if local_signals.spam:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.MEDIUM,
            reason_code=SafetyReason.SPAM,
            requires_adjudication=True,
        )

    for category in active:
        if category in _CONTEXT_SENSITIVE_CATEGORIES:
            return SafetyPolicyResult(
                decision=SafetyDecision.REVIEW,
                risk_level=SafetyRiskLevel.MEDIUM,
                reason_code=_reason_for_category(
                    category
                ),
                requires_adjudication=True,
            )

    if moderation.flagged:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.MEDIUM,
            reason_code=SafetyReason.PROVIDER_FLAGGED,
            requires_adjudication=True,
        )

    if force_contextual_review:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.LOW,
            reason_code=SafetyReason.ADJUDICATION_REQUIRED,
            requires_adjudication=True,
        )

    return SafetyPolicyResult(
        decision=SafetyDecision.ALLOW,
        risk_level=SafetyRiskLevel.LOW,
        reason_code=SafetyReason.SAFE,
        requires_adjudication=False,
    )


def evaluate_image_policy(
    *,
    moderation: ProviderModerationResult,
    context: str = SafetyContext.GENERIC,
) -> SafetyPolicyResult:
    """
    Convert provider image signals into TownLIT policy.

    Image categories are context-adjudicated rather than immediately
    blocked because legitimate documentary, medical, testimony, prayer,
    historical, or recovery imagery may trigger visual safety signals.
    """

    active = active_moderation_categories_for_input(
        moderation,
        input_type="image",
    )

    for category in active:
        if category not in _IMAGE_CONTEXTUAL_CATEGORIES:
            continue

        risk_level = (
            SafetyRiskLevel.HIGH
            if category in _IMAGE_HIGH_RISK_CATEGORIES
            else SafetyRiskLevel.MEDIUM
        )

        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=risk_level,
            reason_code=_reason_for_category(
                category
            ),
            requires_adjudication=True,
        )

    if moderation.flagged:
        return SafetyPolicyResult(
            decision=SafetyDecision.REVIEW,
            risk_level=SafetyRiskLevel.MEDIUM,
            reason_code=SafetyReason.PROVIDER_FLAGGED,
            requires_adjudication=True,
        )

    return SafetyPolicyResult(
        decision=SafetyDecision.ALLOW,
        risk_level=SafetyRiskLevel.LOW,
        reason_code=SafetyReason.SAFE,
        requires_adjudication=False,
    )