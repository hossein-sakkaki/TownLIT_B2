# apps/organizations/tests/test_phase1_core_hardening.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-22.
# Last Update by Hossein Sakkaki on 2026-09-22.
#

from types import SimpleNamespace

from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings

from apps.organizations.admin.memberships import OrganizationMembershipAdmin
from apps.organizations.admin.organizations import OrganizationAdmin
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.services.profile import update_organization_profile


class OrganizationAdminLifecycleGuardTests(SimpleTestCase):
    def test_organization_lifecycle_fields_are_read_only(self):
        model_admin = OrganizationAdmin(Organization, AdminSite())

        self.assertTrue(
            {"status", "suspended_at", "closed_at"}.issubset(
                set(model_admin.get_readonly_fields(request=None))
            )
        )

    def test_membership_lifecycle_fields_are_read_only(self):
        model_admin = OrganizationMembershipAdmin(
            OrganizationMembership,
            AdminSite(),
        )

        self.assertTrue(
            {"status", "suspended_at", "ended_at", "end_reason"}.issubset(
                set(model_admin.get_readonly_fields(request=None))
            )
        )


class OrganizationProfileFeatureFlagTests(TestCase):
    @override_settings(TOWNLIT_ORGANIZATIONS_ENABLED=False)
    def test_profile_service_rejects_mutations_when_master_flag_is_off(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Organizations are currently unavailable.",
        ):
            update_organization_profile(
                organization=SimpleNamespace(pk=-1),
                actor=None,
                validated_data={"name": "Blocked update"},
            )
