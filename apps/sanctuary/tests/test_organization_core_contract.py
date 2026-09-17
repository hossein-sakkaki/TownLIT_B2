# apps/sanctuary/tests/test_organization_core_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.organizations.constants import (
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import Organization
from apps.sanctuary.constants.target_models import (
    ORGANIZATION_TARGET_MODELS,
)
from apps.sanctuary.services.link_resolver import (
    resolve_sanctuary_target_link,
)
from apps.sanctuary.services.ownership import (
    get_owner_user_ids,
    register_default_resolvers,
)
from apps.sanctuary.services.target_access import (
    _validate_organization_target,
)


class SanctuaryOrganizationCoreContractTests(
    SimpleTestCase
):
    def test_organization_content_type_is_canonical(self):
        self.assertEqual(
            ORGANIZATION_TARGET_MODELS,
            frozenset(
                {
                    "organizations.organization",
                }
            ),
        )

    def test_core_organization_link_preserves_web_contract(self):
        organization = Organization(
            id=40,
            name="TownLIT Organization",
            slug="townlit-organization",
        )

        request = SimpleNamespace(
            content_object=organization,
        )

        self.assertEqual(
            resolve_sanctuary_target_link(
                request
            ),
            "/orgs/townlit-organization",
        )

    @patch(
        "apps.sanctuary.services.ownership."
        "effective_organization_manager_user_ids"
    )
    def test_ownership_registry_uses_core_managers(
        self,
        mock_manager_ids,
    ):
        mock_manager_ids.return_value = {
            11,
            12,
        }

        register_default_resolvers()

        organization = Organization(
            id=40,
            name="TownLIT Organization",
            slug="townlit-organization",
        )

        self.assertEqual(
            get_owner_user_ids(
                organization
            ),
            {
                11,
                12,
            },
        )

        mock_manager_ids.assert_called_once_with(
            organization=organization,
        )

    @patch(
        "apps.sanctuary.services.target_access."
        "_organization_manager_user_ids"
    )
    def test_private_organization_is_available_to_current_member(
        self,
        mock_manager_ids,
    ):
        mock_manager_ids.return_value = set()

        memberships = Mock()
        memberships.filter.return_value.exists.return_value = (
            True
        )

        organization = SimpleNamespace(
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PRIVATE,
            memberships=memberships,
        )

        user = SimpleNamespace(
            pk=22,
            is_authenticated=True,
            is_staff=False,
        )

        owner_id, is_manager = (
            _validate_organization_target(
                user=user,
                target=organization,
            )
        )

        self.assertIsNone(
            owner_id
        )
        self.assertFalse(
            is_manager
        )