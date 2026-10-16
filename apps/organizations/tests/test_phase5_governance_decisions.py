# apps/organizations/tests/test_phase5_governance_decisions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations.constants import (
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationGovernanceAction,
    OrganizationKind,
    OrganizationMembershipStatus,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import (
    Organization,
    OrganizationConnection,
    OrganizationMembership,
)
from apps.organizations.services.governance import (
    bootstrap_organization_governance,
    create_governance_proposal,
    governance_owner_target_memberships,
)
from apps.organizations.services.roles import (
    assign_organization_role,
    bootstrap_organization_access,
    get_owner_role,
)
from apps.organizations.views.governance import (
    OrganizationGovernanceOwnerCandidatesView,
)
from apps.profiles.models.member import Member
from apps.subscriptions.models import SubscriptionAccount


@override_settings(
    TOWNLIT_ORGANIZATIONS_ENABLED=True,
    TOWNLIT_ORGANIZATIONS_GOVERNANCE_ENABLED=True,
)
class OrganizationPhase5GovernanceDecisionTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            email="phase5-staff@townlit.test",
            password="test-password",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

        self.organization = Organization.objects.create(
            name="Phase Five Organization",
            slug="phase-five-organization",
            kind=OrganizationKind.NONPROFIT,
            subscription_account=SubscriptionAccount.objects.create(),
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
        )
        bootstrap_organization_access(self.organization)
        bootstrap_organization_governance(self.organization)

    def _create_membership(self, *, email):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email=email,
            password="test-password",
        )
        member = Member.objects.create(
            user=user,
            denomination_branch="",
        )
        connection = OrganizationConnection.objects.create(
            organization=self.organization,
            user=user,
            relationship_type=OrganizationConnectionType.MEMBER,
            status=OrganizationConnectionStatus.ACTIVE,
        )
        return OrganizationMembership.objects.create(
            organization=self.organization,
            member=member,
            connection=connection,
            status=OrganizationMembershipStatus.ACTIVE,
        )

    def _make_owner(self, membership):
        return assign_organization_role(
            membership=membership,
            role=get_owner_role(self.organization),
            actor=self.staff,
            bypass_protection=True,
        )

    def test_final_owner_is_not_available_for_owner_removal(self):
        owner = self._create_membership(
            email="sole-owner@townlit.test",
        )
        self._make_owner(owner)

        candidates = governance_owner_target_memberships(
            organization=self.organization,
            action_key=OrganizationGovernanceAction.OWNER_REMOVAL,
        )

        self.assertFalse(candidates.exists())

        with self.assertRaisesMessage(
            ValidationError,
            "The final organization owner cannot be removed.",
        ):
            create_governance_proposal(
                organization=self.organization,
                actor=self.staff,
                action_key=OrganizationGovernanceAction.OWNER_REMOVAL,
                title="Remove final owner",
                target_membership=owner,
            )

    def test_owner_removal_candidates_are_available_with_two_owners(self):
        first_owner = self._create_membership(
            email="first-owner@townlit.test",
        )
        second_owner = self._create_membership(
            email="second-owner@townlit.test",
        )
        self._make_owner(first_owner)
        self._make_owner(second_owner)

        candidate_ids = set(
            governance_owner_target_memberships(
                organization=self.organization,
                action_key=OrganizationGovernanceAction.OWNER_REMOVAL,
            ).values_list("public_id", flat=True)
        )

        self.assertEqual(
            candidate_ids,
            {first_owner.public_id, second_owner.public_id},
        )

    def test_owner_candidate_endpoint_rejects_non_owner_action(self):
        request = APIRequestFactory().get(
            "/organizations/phase-five-organization/governance/owner-candidates/",
            {"action_key": OrganizationGovernanceAction.ORGANIZATION_CLOSURE},
        )
        force_authenticate(request, user=self.staff)

        response = OrganizationGovernanceOwnerCandidatesView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("action_key", response.data)
