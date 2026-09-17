# apps/accounts/tests/test_litshield_organization_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase

from apps.accounts.models import (
    LITShieldGrant,
    OrganizationLITShieldEndorsement,
)
from apps.organizations.models import Organization


class LITShieldOrganizationContractTests(
    SimpleTestCase
):
    def test_grant_uses_organization_core(self):
        field = LITShieldGrant._meta.get_field(
            "organization"
        )

        self.assertIs(
            field.remote_field.model,
            Organization,
        )

    def test_endorsement_uses_organization_core(self):
        field = (
            OrganizationLITShieldEndorsement
            ._meta
            .get_field("organization")
        )

        self.assertIs(
            field.remote_field.model,
            Organization,
        )

    def test_litshield_grant_remains_one_to_one_per_user(
        self,
    ):
        field = LITShieldGrant._meta.get_field(
            "user"
        )

        self.assertTrue(
            field.one_to_one
        )

    def test_grant_sources_remain_stable(self):
        self.assertEqual(
            LITShieldGrant.DIRECT,
            "direct",
        )

        self.assertEqual(
            LITShieldGrant.ORG_ENDORSEMENT,
            "org_endorsement",
        )