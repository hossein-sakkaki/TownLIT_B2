# apps/accounts/tests/test_townlit_organization_score.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-13.
# Last Update by Hossein Sakkaki on 2026-09-13.
#

from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.accounts.services.townlit_score import (
    _count_member_organization_memberships,
)
from apps.organizations.constants import (
    CURRENT_MEMBERSHIP_STATUSES,
)


class TownLITOrganizationScoreTests(
    SimpleTestCase
):
    @patch(
        "apps.accounts.services."
        "townlit_score."
        "OrganizationMembership.objects.filter"
    )
    def test_counts_canonical_current_memberships(
        self,
        mock_filter,
    ):
        queryset = Mock()
        queryset.count.return_value = 2
        mock_filter.return_value = queryset

        member = object()

        result = (
            _count_member_organization_memberships(
                member
            )
        )

        self.assertEqual(
            result,
            2,
        )

        mock_filter.assert_called_once_with(
            member=member,
            status__in=(
                CURRENT_MEMBERSHIP_STATUSES
            ),
        )

        queryset.count.assert_called_once_with()