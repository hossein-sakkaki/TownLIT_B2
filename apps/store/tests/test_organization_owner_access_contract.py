# apps/store/tests/test_organization_owner_access_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.store.services.organization_access import (
    user_owns_organization,
)


class StoreOrganizationOwnerAccessContractTests(
    SimpleTestCase
):
    @patch(
        "apps.store.services.organization_access."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    def test_owner_access_uses_core_owner_selector(
        self,
        mock_selector,
    ):
        user = Mock()
        user.is_authenticated = True

        organization = Mock()

        queryset = Mock()
        queryset.filter.return_value.exists.return_value = (
            True
        )
        mock_selector.return_value = queryset

        result = user_owns_organization(
            user=user,
            organization=organization,
        )

        self.assertTrue(result)

        queryset.filter.assert_called_once_with(
            member__user=user,
            organization=organization,
        )