# apps/organizations/tests/test_account_deletion_guard.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.organizations.services.account_deletion import (
    ensure_user_can_be_permanently_deleted,
)


class OrganizationAccountDeletionGuardTests(
    SimpleTestCase
):
    @patch(
        "apps.organizations.services."
        "account_deletion."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    def test_non_owner_can_continue(
        self,
        mock_selector,
    ):
        queryset = Mock()
        queryset.filter.return_value.exists.return_value = (
            False
        )
        mock_selector.return_value = queryset

        user = SimpleNamespace(id=10)

        ensure_user_can_be_permanently_deleted(
            user=user,
        )

        queryset.filter.assert_called_once_with(
            member__user=user,
        )

    @patch(
        "apps.organizations.services."
        "account_deletion."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    def test_effective_owner_blocks_permanent_deletion(
        self,
        mock_selector,
    ):
        queryset = Mock()
        queryset.filter.return_value.exists.return_value = (
            True
        )
        mock_selector.return_value = queryset

        user = SimpleNamespace(id=10)

        with self.assertRaises(
            ValidationError
        ):
            ensure_user_can_be_permanently_deleted(
                user=user,
            )
            