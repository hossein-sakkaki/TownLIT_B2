# apps/subscriptions/tests/test_organization_subscription_eligibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.test import SimpleTestCase

from apps.subscriptions.services.eligibility import (
    SubscriptionEligibilityCode,
    ensure_subscription_account_eligible,
    resolve_subscription_account_eligibility,
)


class _GenericAccount:
    status = "active"

    @property
    def organization(self):
        raise ObjectDoesNotExist


class OrganizationSubscriptionEligibilityTests(SimpleTestCase):
    def test_active_generic_account_remains_eligible(self):
        result = resolve_subscription_account_eligibility(
            account=_GenericAccount(),
        )

        self.assertTrue(result.eligible)
        self.assertEqual(
            result.code,
            SubscriptionEligibilityCode.ELIGIBLE,
        )
        self.assertIsNone(result.is_verified)

    def test_inactive_account_is_not_eligible(self):
        account = SimpleNamespace(
            status="suspended",
        )

        result = resolve_subscription_account_eligibility(
            account=account,
        )

        self.assertFalse(result.eligible)
        self.assertEqual(
            result.code,
            SubscriptionEligibilityCode.ACCOUNT_UNAVAILABLE,
        )

    @patch(
        "apps.organizations.selectors.verification.is_organization_verified",
        return_value=False,
    )
    def test_unverified_organization_is_not_eligible(self, _):
        organization = SimpleNamespace(
            status="active",
        )
        account = SimpleNamespace(
            status="active",
            organization=organization,
        )

        result = resolve_subscription_account_eligibility(
            account=account,
        )

        self.assertFalse(result.eligible)
        self.assertEqual(
            result.code,
            SubscriptionEligibilityCode.VERIFICATION_REQUIRED,
        )
        self.assertFalse(result.is_verified)

    @patch(
        "apps.organizations.selectors.verification.is_organization_verified",
        return_value=True,
    )
    def test_verified_organization_is_eligible(self, _):
        organization = SimpleNamespace(
            status="active",
        )
        account = SimpleNamespace(
            status="active",
            organization=organization,
        )

        result = resolve_subscription_account_eligibility(
            account=account,
        )

        self.assertTrue(result.eligible)
        self.assertEqual(
            result.code,
            SubscriptionEligibilityCode.ELIGIBLE,
        )
        self.assertTrue(result.is_verified)

    @patch(
        "apps.organizations.selectors.verification.is_organization_verified",
        return_value=True,
    )
    def test_organization_rejects_non_organization_plan(self, _):
        organization = SimpleNamespace(
            status="active",
        )
        account = SimpleNamespace(
            status="active",
            organization=organization,
        )
        plan = SimpleNamespace(
            audience_key="member",
        )

        result = resolve_subscription_account_eligibility(
            account=account,
            plan=plan,
        )

        self.assertFalse(result.eligible)
        self.assertEqual(
            result.code,
            SubscriptionEligibilityCode.PLAN_AUDIENCE_MISMATCH,
        )

    @patch(
        "apps.organizations.selectors.verification.is_organization_verified",
        return_value=False,
    )
    def test_enforcement_raises_for_unverified_organization(self, _):
        organization = SimpleNamespace(
            status="active",
        )
        account = SimpleNamespace(
            status="active",
            organization=organization,
        )

        with self.assertRaises(ValidationError):
            ensure_subscription_account_eligible(
                account=account,
            )
