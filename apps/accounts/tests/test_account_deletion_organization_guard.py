# apps/accounts/tests/test_account_deletion_organization_guard.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.accounts.account_deletion.exceptions import (
    AccountDeletionBlocked,
)
from apps.accounts.account_deletion.service import (
    _ensure_organization_ownership_allows_account_deletion,
)


class AccountDeletionOrganizationGuardTests(
    SimpleTestCase
):
    @patch(
        "apps.accounts.account_deletion.service."
        "ensure_user_can_be_permanently_deleted"
    )
    def test_non_owner_can_continue(
        self,
        mock_guard,
    ):
        user = SimpleNamespace(id=17)

        _ensure_organization_ownership_allows_account_deletion(
            user=user,
        )

        mock_guard.assert_called_once_with(
            user=user,
        )

    @patch(
        "apps.accounts.account_deletion.service."
        "ensure_user_can_be_permanently_deleted"
    )
    def test_owner_block_is_translated_to_account_deletion_contract(
        self,
        mock_guard,
    ):
        mock_guard.side_effect = ValidationError(
            (
                "Account deletion cannot be completed "
                "while the account holds active "
                "Organization ownership."
            )
        )

        user = SimpleNamespace(id=17)

        with self.assertRaises(
            AccountDeletionBlocked
        ) as raised:
            _ensure_organization_ownership_allows_account_deletion(
                user=user,
            )

        self.assertEqual(
            raised.exception.code,
            (
                "organization_ownership_blocks_"
                "account_deletion"
            ),
        )

        self.assertIn(
            "Organization ownership",
            raised.exception.message,
        )