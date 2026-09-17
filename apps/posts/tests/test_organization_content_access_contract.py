# apps/posts/tests/test_organization_content_access_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.organizations.constants import (
    OrganizationPermissionKey,
)
from apps.organizations.models import Organization
from apps.organizations.permissions import (
    OrganizationsEnabledPermission,
)
from apps.posts.mixins import mixins as posts_mixins
from apps.posts.services.organization_access import (
    can_manage_organization_content,
)
from apps.posts.views.witnesses import WitnessViewSet


class OrganizationContentAccessContractTests(
    SimpleTestCase
):
    @patch(
        "apps.posts.services.organization_access."
        "user_has_organization_permission"
    )
    def test_content_access_uses_core_manage_content_permission(
        self,
        mock_permission,
    ):
        mock_permission.return_value = True

        user = SimpleNamespace(
            id=7,
        )
        organization = SimpleNamespace(
            id=19,
        )

        allowed = can_manage_organization_content(
            user=user,
            organization=organization,
        )

        self.assertTrue(allowed)

        mock_permission.assert_called_once_with(
            user=user,
            organization=organization,
            permission_key=(
                OrganizationPermissionKey
                .MANAGE_CONTENT
            ),
        )

    def test_organization_action_mixin_uses_core_model(
        self,
    ):
        self.assertIs(
            posts_mixins.Organization,
            Organization,
        )

    def test_witness_view_uses_core_model(
        self,
    ):
        from apps.posts.views import witnesses

        self.assertIs(
            witnesses.Organization,
            Organization,
        )

    def test_witness_view_is_feature_flagged(
        self,
    ):
        self.assertIn(
            OrganizationsEnabledPermission,
            WitnessViewSet.permission_classes,
        )