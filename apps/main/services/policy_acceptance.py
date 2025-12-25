# apps/main/services/policy_acceptance.py

from typing import Iterable
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.main.models import TermsAndPolicy, UserAgreement


# ---------------------------------------------------------
# Low-level helper
# - Idempotent
# - History-safe
# - One latest agreement per (user, policy)
# ---------------------------------------------------------
@transaction.atomic
def ensure_policy_acceptance(*, user, policy: TermsAndPolicy) -> UserAgreement:
    """
    Ensure user has accepted the given policy.
    Safe to call multiple times.
    """

    if not user:
        raise ValidationError("User is required for policy acceptance.")

    if not policy:
        raise ValidationError("Policy is required for policy acceptance.")

    agreement = UserAgreement.objects.filter(
        user=user,
        policy=policy,
        is_latest_agreement=True,
    ).first()

    if agreement:
        return agreement

    return UserAgreement.objects.create(
        user=user,
        policy=policy,
        is_latest_agreement=True,
    )


# ---------------------------------------------------------
# High-level helper
# - Context-aware (registration / sanctuary / feature / etc.)
# - Language-aware with EN fallback
# ---------------------------------------------------------
def accept_required_policies(
    *,
    user,
    acceptance_context: str,
    language: str = "en",
) -> list[UserAgreement]:
    """
    Accept all required policies for a given context.
    Example contexts:
      - registration
      - sanctuary
      - login
      - feature_sensitive
    """

    if not user:
        raise ValidationError("User is required.")

    qs = TermsAndPolicy.objects.filter(
        requires_acceptance=True,
        acceptance_context=acceptance_context,
        is_active=True,
        language=language,
    ).order_by("-last_updated")

    # Fallback to EN
    if not qs.exists() and language != "en":
        qs = TermsAndPolicy.objects.filter(
            requires_acceptance=True,
            acceptance_context=acceptance_context,
            is_active=True,
            language="en",
        ).order_by("-last_updated")

    if not qs.exists():
        raise ValidationError(
            f"No active required policies found for context '{acceptance_context}'."
        )

    accepted: list[UserAgreement] = []

    for policy in qs:
        agreement = ensure_policy_acceptance(user=user, policy=policy)
        accepted.append(agreement)

    return accepted


# ---------------------------------------------------------
# Query helper (for frontend / guards)
# ---------------------------------------------------------
def get_missing_required_policies(
    *,
    user,
    acceptance_context: str,
    language: str = "en",
) -> Iterable[TermsAndPolicy]:
    """
    Return policies that user has NOT yet accepted
    for the given context.
    """

    if not user:
        return []

    required_qs = TermsAndPolicy.objects.filter(
        requires_acceptance=True,
        acceptance_context=acceptance_context,
        is_active=True,
        language=language,
    )

    accepted_policy_ids = UserAgreement.objects.filter(
        user=user,
        is_latest_agreement=True,
    ).values_list("policy_id", flat=True)

    return required_qs.exclude(id__in=accepted_policy_ids)
