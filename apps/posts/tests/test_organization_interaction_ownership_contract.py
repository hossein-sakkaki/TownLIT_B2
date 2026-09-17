# apps/posts/tests/test_organization_interaction_ownership_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.organizations.models import Organization
from apps.posts.services.boundary_interactions import (
    check_target_owner_boundary,
    resolve_owner_user,
)
from apps.posts.views.reactions import (
    _resolve_owner_user_id,
)


class OrganizationInteractionOwnershipContractTests(
    SimpleTestCase
):
    def test_organization_creator_is_not_direct_owner(
        self,
    ):
        creator = SimpleNamespace(
            id=11,
        )

        organization = Organization(
            id=40,
            name="Core Organization",
            slug="core-organization",
        )

        organization.created_by_id = 11

        self.assertIsNone(
            resolve_owner_user(
                organization
            )
        )

    @patch(
        "apps.posts.views.reactions."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    def test_reaction_owner_resolution_uses_core_ownership(
        self,
        mock_selector,
    ):
        organization = Organization(
            id=40,
            name="Core Organization",
            slug="core-organization",
        )

        queryset = Mock()
        queryset.filter.return_value.exists.return_value = (
            True
        )
        mock_selector.return_value = queryset

        result = _resolve_owner_user_id(
            organization,
            request_user_id=77,
        )

        self.assertEqual(
            result,
            77,
        )

        queryset.filter.assert_called_once_with(
            organization=organization,
            member__user_id=77,
        )

    @patch(
        "apps.posts.views.reactions."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    def test_non_owner_cannot_open_organization_reaction_inbox(
        self,
        mock_selector,
    ):
        organization = Organization(
            id=40,
            name="Core Organization",
            slug="core-organization",
        )

        queryset = Mock()
        queryset.filter.return_value.exists.return_value = (
            False
        )
        mock_selector.return_value = queryset

        result = _resolve_owner_user_id(
            organization,
            request_user_id=77,
        )

        self.assertIsNone(result)

    @patch(
        "apps.posts.services.boundary_interactions."
        "get_target_object"
    )
    @patch(
        "apps.posts.services.boundary_interactions."
        "effective_organization_owner_"
        "memberships_queryset"
    )
    @patch(
        "apps.posts.services.boundary_interactions."
        "BoundaryPolicy.has_boundary_between"
    )
    def test_boundary_checks_all_effective_organization_owners(
        self,
        mock_boundary,
        mock_selector,
        mock_target,
    ):
        organization = Organization(
            id=40,
            name="Core Organization",
            slug="core-organization",
        )

        actor = SimpleNamespace(
            id=1,
        )
        owner_one = SimpleNamespace(
            id=2,
        )
        owner_two = SimpleNamespace(
            id=3,
        )

        membership_one = SimpleNamespace(
            member=SimpleNamespace(
                user=owner_one,
            )
        )
        membership_two = SimpleNamespace(
            member=SimpleNamespace(
                user=owner_two,
            )
        )

        queryset = Mock()
        queryset.filter.return_value.select_related.return_value.iterator.return_value = iter(
            [
                membership_one,
                membership_two,
            ]
        )

        mock_selector.return_value = queryset
        mock_target.return_value = organization

        mock_boundary.side_effect = (
            lambda first, second:
            second.id == owner_two.id
        )

        result = check_target_owner_boundary(
            actor=actor,
            content_type=Mock(),
            object_id=40,
        )

        self.assertFalse(
            result.allowed
        )
        self.assertEqual(
            result.counterpart_id,
            owner_two.id,
        )