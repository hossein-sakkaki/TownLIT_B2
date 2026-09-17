# apps/organizations/tests/test_owner_selector_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationRoleKey,
)
from apps.organizations.models import (
    OrganizationMembership,
)
from apps.organizations.selectors.ownership import (
    effective_organization_owner_memberships_queryset,
)


class OrganizationOwnerSelectorContractTests(
    SimpleTestCase
):
    def test_owner_selector_targets_canonical_membership(self):
        queryset = (
            effective_organization_owner_memberships_queryset(
                now=timezone.now(),
            )
        )

        self.assertIs(
            queryset.model,
            OrganizationMembership,
        )

    def test_owner_role_key_remains_stable(self):
        self.assertEqual(
            OrganizationRoleKey.OWNER,
            "owner",
        )