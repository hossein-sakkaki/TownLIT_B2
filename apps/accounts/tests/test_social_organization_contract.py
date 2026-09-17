# apps/accounts/tests/test_social_organization_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.accounts.services.social_links import (
    SOCIAL_OWNER_ORGANIZATION,
    SOCIAL_OWNER_USER,
    resolve_social_owner_for_management,
)
from apps.organizations.constants import (
    OrganizationPermissionKey,
)


class SocialOrganizationContractTests(
    SimpleTestCase
):
    def test_user_can_manage_own_social_owner(self):
        actor = SimpleNamespace(id=42)

        resolved = (
            resolve_social_owner_for_management(
                actor=actor,
                content_type_key=(
                    SOCIAL_OWNER_USER
                ),
                object_id=42,
            )
        )

        self.assertIs(
            resolved,
            actor,
        )

    @patch(
        "apps.accounts.services.social_links."
        "organizations_enabled",
        return_value=True,
    )
    @patch(
        "apps.accounts.services.social_links."
        "user_has_organization_permission",
        return_value=True,
    )
    @patch(
        "apps.accounts.services.social_links."
        "Organization.objects.filter"
    )
    def test_organization_social_management_uses_profile_permission(
        self,
        mock_filter,
        mock_permission,
        mock_enabled,
    ):
        actor = SimpleNamespace(id=7)
        organization = Mock()

        mock_filter.return_value.first.return_value = (
            organization
        )

        resolved = (
            resolve_social_owner_for_management(
                actor=actor,
                content_type_key=(
                    SOCIAL_OWNER_ORGANIZATION
                ),
                object_id=19,
            )
        )

        self.assertIs(
            resolved,
            organization,
        )

        mock_filter.assert_called_once_with(
            pk=19,
        )

        mock_permission.assert_called_once_with(
            user=actor,
            organization=organization,
            permission_key=(
                OrganizationPermissionKey
                .MANAGE_PROFILE
            ),
        )

    @patch(
        "apps.accounts.services.social_links."
        "organizations_enabled",
        return_value=False,
    )
    def test_organization_social_management_fails_closed(
        self,
        mock_enabled,
    ):
        actor = SimpleNamespace(id=7)

        resolved = (
            resolve_social_owner_for_management(
                actor=actor,
                content_type_key=(
                    SOCIAL_OWNER_ORGANIZATION
                ),
                object_id=19,
            )
        )

        self.assertIsNone(resolved)