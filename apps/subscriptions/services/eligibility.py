# apps/subscriptions/services/eligibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

from apps.subscriptions.constants import (
    ORGANIZATION_SUBSCRIPTION_AUDIENCE_KEY,
    SubscriptionAccountStatus,
)


class SubscriptionEligibilityCode:
    ELIGIBLE = "eligible"
    ACCOUNT_UNAVAILABLE = "subscription_account_unavailable"
    ORGANIZATION_INACTIVE = "organization_inactive"
    VERIFICATION_REQUIRED = "verification_required"
    PLAN_AUDIENCE_MISMATCH = "plan_audience_mismatch"


@dataclass(frozen=True)
class SubscriptionEligibilityResult:
    eligible: bool
    code: str
    detail: str
    is_verified: bool | None = None

    def as_dict(self) -> dict:
        return {
            "eligible": self.eligible,
            "code": self.code,
            "detail": self.detail,
            "is_verified": self.is_verified,
        }


def resolve_subscription_account_eligibility(
    *,
    account,
    plan=None,
    now=None,
) -> SubscriptionEligibilityResult:
    """
    Resolve the canonical prerequisites for starting or activating a
    subscription on a SubscriptionAccount.

    Organization accounts require an active Organization and effective
    TownLIT Organization verification. Existing subscriptions are not
    canceled when verification later changes; service/module authorization
    remains responsible for runtime access.
    """
    now = now or timezone.now()
    organization = _organization_for_account(account)

    verified = None
    organization_status = None

    if organization is not None:
        # Lazy imports keep the generic subscriptions app independent at import time.
        from apps.organizations.constants import OrganizationStatus
        from apps.organizations.selectors.verification import (
            is_organization_verified,
        )

        organization_status = organization.status
        verified = is_organization_verified(
            organization=organization,
            now=now,
        )

    if account.status != SubscriptionAccountStatus.ACTIVE:
        return SubscriptionEligibilityResult(
            eligible=False,
            code=SubscriptionEligibilityCode.ACCOUNT_UNAVAILABLE,
            detail="Subscription account is not active.",
            is_verified=verified,
        )

    if organization is None:
        return SubscriptionEligibilityResult(
            eligible=True,
            code=SubscriptionEligibilityCode.ELIGIBLE,
            detail="Subscription account is eligible.",
            is_verified=None,
        )

    if organization_status != OrganizationStatus.ACTIVE:
        return SubscriptionEligibilityResult(
            eligible=False,
            code=SubscriptionEligibilityCode.ORGANIZATION_INACTIVE,
            detail=(
                "Only active Organizations can start or activate a subscription."
            ),
            is_verified=bool(verified),
        )

    if not verified:
        return SubscriptionEligibilityResult(
            eligible=False,
            code=SubscriptionEligibilityCode.VERIFICATION_REQUIRED,
            detail=(
                "Organization verification is required before starting or "
                "activating a subscription."
            ),
            is_verified=False,
        )

    if (
        plan is not None
        and plan.audience_key != ORGANIZATION_SUBSCRIPTION_AUDIENCE_KEY
    ):
        return SubscriptionEligibilityResult(
            eligible=False,
            code=SubscriptionEligibilityCode.PLAN_AUDIENCE_MISMATCH,
            detail=(
                "This subscription plan is not available for Organization accounts."
            ),
            is_verified=True,
        )

    return SubscriptionEligibilityResult(
        eligible=True,
        code=SubscriptionEligibilityCode.ELIGIBLE,
        detail=(
            "This Organization meets the prerequisites for subscription activation."
        ),
        is_verified=True,
    )


def ensure_subscription_account_eligible(
    *,
    account,
    plan=None,
    now=None,
) -> SubscriptionEligibilityResult:
    result = resolve_subscription_account_eligibility(
        account=account,
        plan=plan,
        now=now,
    )

    if not result.eligible:
        raise ValidationError(result.detail)

    return result


def _organization_for_account(account):
    try:
        return account.organization
    except (ObjectDoesNotExist, AttributeError):
        return None
