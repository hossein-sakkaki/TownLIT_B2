# apps/organizations/tests/test_phase6_administration.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations.constants import (
    OrganizationAuditAction,
    OrganizationAuditSource,
    OrganizationConnectionStatus,
    OrganizationConnectionType,
    OrganizationKind,
    OrganizationMembershipStatus,
    OrganizationRoleKey,
    OrganizationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import (
    Organization,
    OrganizationAuditLog,
    OrganizationConnection,
    OrganizationMembership,
)
from apps.organizations.services.roles import (
    assign_organization_role,
    bootstrap_organization_access,
    get_owner_role,
)
from apps.organizations.views.administration import (
    OrganizationAdministrationOverviewView,
    OrganizationAuditActivityView,
)
from apps.profiles.models.member import Member
from apps.subscriptions.models import SubscriptionAccount


@override_settings(
    TOWNLIT_ORGANIZATIONS_ENABLED=True,
)
class OrganizationPhase6AdministrationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()

        self.owner_user = user_model.objects.create_user(
            email="phase6-owner@townlit.test",
            password="test-password",
        )
        self.staff = user_model.objects.create_user(
            email="phase6-staff@townlit.test",
            password="test-password",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

        self.organization = Organization.objects.create(
            name="Phase Six Organization",
            slug="phase-six-organization",
            kind=OrganizationKind.NONPROFIT,
            subscription_account=SubscriptionAccount.objects.create(),
            status=OrganizationStatus.ACTIVE,
            visibility=OrganizationVisibility.PUBLIC,
        )
        bootstrap_organization_access(self.organization)

        member = Member.objects.create(
            user=self.owner_user,
            denomination_branch="",
        )
        connection = OrganizationConnection.objects.create(
            organization=self.organization,
            user=self.owner_user,
            relationship_type=OrganizationConnectionType.MEMBER,
            status=OrganizationConnectionStatus.ACTIVE,
        )
        self.membership = OrganizationMembership.objects.create(
            organization=self.organization,
            member=member,
            connection=connection,
            status=OrganizationMembershipStatus.ACTIVE,
        )
        assign_organization_role(
            membership=self.membership,
            role=get_owner_role(self.organization),
            actor=self.staff,
            bypass_protection=True,
        )

        OrganizationAuditLog.objects.filter(
            organization=self.organization
        ).delete()

        self.factory = APIRequestFactory()

    def test_lifecycle_overview_returns_authoritative_status_dates(self):
        request = self.factory.get(
            "/organizations/phase-six-organization/administration/overview/"
        )
        force_authenticate(request, user=self.owner_user)

        response = OrganizationAdministrationOverviewView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], OrganizationStatus.ACTIVE)
        self.assertEqual(response.data["slug"], self.organization.slug)
        self.assertIsNone(response.data["suspended_at"])
        self.assertIsNone(response.data["closed_at"])

    def test_client_activity_hides_raw_metadata_and_private_events(self):
        OrganizationAuditLog.objects.create(
            organization=self.organization,
            action=OrganizationAuditAction.ORGANIZATION_UPDATED,
            source=OrganizationAuditSource.SERVICE,
            actor=self.owner_user,
            metadata={"internal_secret": "do-not-expose"},
        )
        OrganizationAuditLog.objects.create(
            organization=self.organization,
            action=OrganizationAuditAction.FOLLOWED,
            source=OrganizationAuditSource.SERVICE,
            actor=self.owner_user,
            target_user=self.owner_user,
        )
        OrganizationAuditLog.objects.create(
            organization=self.organization,
            action=OrganizationAuditAction.GOVERNANCE_VOTE_CAST,
            source=OrganizationAuditSource.GOVERNANCE,
            actor=self.owner_user,
            metadata={"choice": "approve"},
        )
        OrganizationAuditLog.objects.create(
            organization=self.organization,
            action=OrganizationAuditAction.VERIFICATION_REJECTED,
            source=OrganizationAuditSource.ADMIN,
            actor=self.staff,
            metadata={"reason": "internal reviewer note"},
        )

        request = self.factory.get(
            "/organizations/phase-six-organization/administration/activity/"
        )
        force_authenticate(request, user=self.owner_user)

        response = OrganizationAuditActivityView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(response.status_code, 200)

        actions = {
            item["action"]
            for item in response.data["results"]
        }
        self.assertEqual(
            actions,
            {
                OrganizationAuditAction.ORGANIZATION_UPDATED,
                OrganizationAuditAction.VERIFICATION_REJECTED,
            },
        )

        for item in response.data["results"]:
            self.assertNotIn("metadata", item)

        admin_event = next(
            item
            for item in response.data["results"]
            if item["action"] == OrganizationAuditAction.VERIFICATION_REJECTED
        )
        self.assertIsNone(admin_event["actor"])
        self.assertEqual(admin_event["actor_label"], "TownLIT")


    def test_billing_manager_cannot_read_cross_domain_audit_feed(self):
        user_model = get_user_model()
        billing_user = user_model.objects.create_user(
            email="phase6-billing@townlit.test",
            password="test-password",
        )
        member = Member.objects.create(
            user=billing_user,
            denomination_branch="",
        )
        connection = OrganizationConnection.objects.create(
            organization=self.organization,
            user=billing_user,
            relationship_type=OrganizationConnectionType.MEMBER,
            status=OrganizationConnectionStatus.ACTIVE,
        )
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            member=member,
            connection=connection,
            status=OrganizationMembershipStatus.ACTIVE,
        )
        billing_role = self.organization.roles.get(
            key=OrganizationRoleKey.BILLING_MANAGER,
            is_active=True,
        )
        assign_organization_role(
            membership=membership,
            role=billing_role,
            actor=self.staff,
        )

        request = self.factory.get(
            "/organizations/phase-six-organization/administration/activity/"
        )
        force_authenticate(request, user=billing_user)

        response = OrganizationAuditActivityView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(response.status_code, 403)

    def test_activity_pagination_uses_before_id(self):
        created = []
        for _ in range(3):
            created.append(
                OrganizationAuditLog.objects.create(
                    organization=self.organization,
                    action=OrganizationAuditAction.ORGANIZATION_UPDATED,
                    source=OrganizationAuditSource.SERVICE,
                    actor=self.owner_user,
                )
            )

        request = self.factory.get(
            "/organizations/phase-six-organization/administration/activity/",
            {"limit": 2},
        )
        force_authenticate(request, user=self.owner_user)

        first = OrganizationAuditActivityView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data["has_more"])
        self.assertEqual(len(first.data["results"]), 2)
        self.assertEqual(
            first.data["next_before_id"],
            first.data["results"][-1]["id"],
        )

        request = self.factory.get(
            "/organizations/phase-six-organization/administration/activity/",
            {
                "limit": 2,
                "before_id": first.data["next_before_id"],
            },
        )
        force_authenticate(request, user=self.owner_user)

        second = OrganizationAuditActivityView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.data["has_more"])
        self.assertEqual(len(second.data["results"]), 1)
        self.assertEqual(second.data["results"][0]["id"], created[0].id)
