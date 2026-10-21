
# apps/organizations/tests/test_settings_production_hardening.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.
#

from datetime import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase

from apps.organizations.constants import (
    OrganizationPermissionKey,
    OrganizationStatus,
)
from apps.organizations.services import (
    lifecycle_policy,
    modules,
    profile,
    profile_details,
    roles,
    verification,
)


class RoleDelegationPolicyTests(SimpleTestCase):
    """Test the real delegation policy without evaluating QuerySets."""

    def setUp(self):
        self.organization = SimpleNamespace(pk=11)
        self.actor = SimpleNamespace(
            is_authenticated=True,
            is_staff=False,
        )

    def _check(
        self,
        *,
        target_permissions=(),
        actor_permissions=(),
        actor_priority=80,
        target_priority=40,
        is_owner=False,
        may_manage_roles=True,
        actor=None,
    ):
        role_permissions = Mock()
        role_permissions.values_list.return_value = list(
            target_permissions
        )

        role = SimpleNamespace(
            priority=target_priority,
            role_permissions=role_permissions,
        )

        assignments = Mock()
        assignments.filter.return_value.exists.return_value = (
            is_owner
        )
        assignments.values_list.return_value = list(
            actor_permissions
        )
        assignments.order_by.return_value.values_list.return_value.first.return_value = (
            actor_priority
        )

        with (
            patch.object(
                roles,
                "user_has_organization_permission_strict",
                return_value=may_manage_roles,
            ),
            patch.object(
                roles,
                "_active_organization_assignments",
                return_value=assignments,
            ),
        ):
            return roles._require_role_delegation(
                actor=self.actor if actor is None else actor,
                organization=self.organization,
                role=role,
            )

    def test_anonymous_actor_is_denied(self):
        anonymous = SimpleNamespace(
            is_authenticated=False,
            is_staff=False,
        )

        with self.assertRaises(PermissionDenied):
            self._check(actor=anonymous)

    def test_actor_without_manage_roles_is_denied(self):
        with self.assertRaises(PermissionDenied):
            self._check(may_manage_roles=False)

    def test_owner_can_delegate_sensitive_roles(self):
        self._check(
            is_owner=True,
            target_permissions=[
                OrganizationPermissionKey.MANAGE_BILLING
            ],
        )

    def test_staff_can_delegate_sensitive_roles(self):
        staff = SimpleNamespace(
            is_authenticated=True,
            is_staff=True,
        )

        self._check(
            actor=staff,
            may_manage_roles=False,
            target_permissions=[
                OrganizationPermissionKey.MANAGE_VERIFICATION
            ],
        )

    def test_manager_can_delegate_subset_at_lower_priority(self):
        self._check(
            actor_permissions=[
                OrganizationPermissionKey.MANAGE_PROFILE
            ],
            target_permissions=[
                OrganizationPermissionKey.MANAGE_PROFILE
            ],
            actor_priority=80,
            target_priority=50,
        )

    def test_non_owner_cannot_delegate_sensitive_permissions(self):
        for permission in (
            OrganizationPermissionKey.MANAGE_BILLING,
            OrganizationPermissionKey.MANAGE_VERIFICATION,
            OrganizationPermissionKey.MANAGE_GOVERNANCE,
        ):
            with self.subTest(permission=permission):
                with self.assertRaises(PermissionDenied):
                    self._check(
                        actor_permissions=[permission],
                        target_permissions=[permission],
                    )

    def test_manager_cannot_delegate_a_permission_they_lack(self):
        with self.assertRaises(PermissionDenied):
            self._check(
                actor_permissions=[
                    OrganizationPermissionKey.MANAGE_PROFILE
                ],
                target_permissions=[
                    OrganizationPermissionKey.MANAGE_MODULES
                ],
            )

    def test_manager_cannot_delegate_higher_priority_role(self):
        with self.assertRaises(PermissionDenied):
            self._check(
                actor_permissions=[
                    OrganizationPermissionKey.MANAGE_PROFILE
                ],
                target_permissions=[
                    OrganizationPermissionKey.MANAGE_PROFILE
                ],
                actor_priority=50,
                target_priority=90,
            )

    def test_manager_without_current_priority_cannot_delegate(self):
        with self.assertRaises(PermissionDenied):
            self._check(actor_priority=None)


class OrganizationLifecyclePolicyTests(SimpleTestCase):
    """Exercise lifecycle checks with in-memory model substitutes."""

    def test_only_active_organizations_pass_lifecycle_guard(self):
        for status in (
            OrganizationStatus.ACTIVE,
            OrganizationStatus.SUSPENDED,
            OrganizationStatus.CLOSED,
        ):
            with self.subTest(status=status):
                organization = SimpleNamespace(
                    pk=11,
                    status=status,
                )

                with patch.object(
                    lifecycle_policy,
                    "Organization",
                ) as model:
                    model.objects.select_for_update.return_value.only.return_value.get.return_value = (
                        organization
                    )

                    if status == OrganizationStatus.ACTIVE:
                        self.assertIs(
                            lifecycle_policy.require_operational_organization(
                                organization=organization
                            ),
                            organization,
                        )
                    else:
                        with self.assertRaises(PermissionDenied):
                            lifecycle_policy.require_operational_organization(
                                organization=organization
                            )

                    model.objects.select_for_update.assert_called_once_with()

    def test_profile_manager_checks_lifecycle_before_permissions(self):
        organization = SimpleNamespace(pk=11)

        with (
            patch.object(
                profile_details,
                "require_operational_organization",
                side_effect=PermissionDenied("Inactive"),
            ),
            patch.object(
                profile_details,
                "user_has_organization_permission",
            ) as check,
        ):
            with self.assertRaises(PermissionDenied):
                profile_details._ensure_profile_manager(
                    organization=organization,
                    actor=object(),
                )

            check.assert_not_called()

    def test_module_and_verification_guards_run_before_permission_checks(self):
        organization = SimpleNamespace(pk=11)

        for service, method_name, permission_name, extras in (
            (
                modules,
                "_require_actor_can_manage_module",
                "_actor_can_manage_module",
                {"module_key": "worship"},
            ),
            (
                verification,
                "_ensure_verification_manager",
                "user_has_organization_permission",
                {},
            ),
        ):
            with self.subTest(service=service.__name__):
                with (
                    patch.object(
                        service,
                        "require_operational_organization",
                        side_effect=PermissionDenied("Inactive"),
                    ),
                    patch.object(
                        service,
                        permission_name,
                    ) as check,
                ):
                    with self.assertRaises(PermissionDenied):
                        getattr(
                            service,
                            method_name,
                        )(
                            organization=organization,
                            actor=SimpleNamespace(
                                is_staff=False
                            ),
                            **extras,
                        )

                    check.assert_not_called()

    def test_profile_update_cannot_write_when_lifecycle_rejects(self):
        organization = SimpleNamespace(
            pk=11,
            status=OrganizationStatus.SUSPENDED,
            name="Old name",
            full_clean=Mock(),
            save=Mock(),
        )

        with (
            patch.object(
                profile,
                "ensure_organizations_enabled",
            ),
            patch.object(
                profile,
                "Organization",
            ) as model,
            patch.object(
                profile,
                "require_operational_organization",
                side_effect=PermissionDenied("Inactive"),
            ),
            patch.object(
                profile,
                "user_has_organization_permission",
            ) as access,
            patch.object(
                profile,
                "OrganizationAuditLog",
            ) as audit,
        ):
            model.objects.select_for_update.return_value.get.return_value = (
                organization
            )

            # Skip transaction.atomic; execute the real service body.
            with self.assertRaises(PermissionDenied):
                profile.update_organization_profile.__wrapped__(
                    organization=organization,
                    actor=object(),
                    validated_data={
                        "name": "Unauthorized change"
                    },
                )

            self.assertEqual(
                organization.name,
                "Old name",
            )

            organization.save.assert_not_called()
            access.assert_not_called()
            audit.objects.create.assert_not_called()

    def test_assign_and_revoke_check_lifecycle_before_db_mutations(self):
        organization = SimpleNamespace(pk=11)

        membership = SimpleNamespace(
            pk=21,
            organization=organization,
        )

        role = SimpleNamespace(pk=31)

        assignment = SimpleNamespace(
            pk=41,
            membership=membership,
        )

        with (
            patch.object(
                roles,
                "require_operational_organization",
                side_effect=PermissionDenied("Inactive"),
            ),
            patch.object(
                roles,
                "OrganizationMembership",
            ) as membership_model,
            patch.object(
                roles,
                "OrganizationRoleAssignment",
            ) as assignment_model,
        ):
            with self.assertRaises(PermissionDenied):
                roles.assign_organization_role.__wrapped__(
                    membership=membership,
                    role=role,
                    actor=object(),
                )

            with self.assertRaises(PermissionDenied):
                roles.revoke_organization_role.__wrapped__(
                    assignment=assignment,
                    actor=object(),
                )

            membership_model.objects.select_for_update.assert_not_called()
            assignment_model.objects.select_for_update.assert_not_called()


class BusinessHoursPolicyTests(SimpleTestCase):
    """Test circular weekly intervals without database records."""

    @staticmethod
    def row(
        weekday,
        opens_at=None,
        closes_at=None,
        sort_order=0,
        **flags,
    ):
        return SimpleNamespace(
            weekday=weekday,
            opens_at=opens_at,
            closes_at=closes_at,
            sort_order=sort_order,
            is_closed=flags.get(
                "is_closed",
                False,
            ),
            is_24_hours=flags.get(
                "is_24_hours",
                False,
            ),
        )

    def validate(self, *rows):
        return profile_details._validate_weekly_business_hours(
            list(rows)
        )

    def test_valid_adjoining_periods(self):
        self.validate(
            self.row(
                0,
                time(9),
                time(12),
            ),
            self.row(
                0,
                time(12),
                time(15),
                sort_order=10,
            ),
        )

    def test_valid_overnight_period_without_conflict(self):
        self.validate(
            self.row(
                0,
                time(22),
                time(2),
            ),
            self.row(
                1,
                time(3),
                time(8),
            ),
        )

    def test_valid_closed_and_24_hour_days(self):
        self.validate(
            self.row(
                0,
                is_closed=True,
            ),
            self.row(
                1,
                is_24_hours=True,
            ),
            self.row(
                2,
                time(8),
                time(12),
            ),
        )

    def test_same_day_overlap_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    0,
                    time(9),
                    time(13),
                ),
                self.row(
                    0,
                    time(12),
                    time(17),
                    sort_order=10,
                ),
            )

    def test_overnight_overlap_next_day_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    0,
                    time(22),
                    time(2),
                ),
                self.row(
                    1,
                    time(1),
                    time(4),
                ),
            )

    def test_sunday_to_monday_overlap_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    6,
                    time(23),
                    time(2),
                ),
                self.row(
                    0,
                    time(1),
                    time(4),
                ),
            )

    def test_overnight_period_conflicts_with_closed_next_day(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    0,
                    time(22),
                    time(2),
                ),
                self.row(
                    1,
                    is_closed=True,
                ),
            )

    def test_special_row_cannot_be_combined_with_regular_row(self):
        for flag in (
            "is_closed",
            "is_24_hours",
        ):
            with self.subTest(flag=flag):
                with self.assertRaises(ValidationError):
                    self.validate(
                        self.row(
                            2,
                            **{flag: True},
                        ),
                        self.row(
                            2,
                            time(8),
                            time(12),
                            sort_order=10,
                        ),
                    )

    def test_duplicate_sort_order_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    0,
                    time(8),
                    time(10),
                ),
                self.row(
                    0,
                    time(10),
                    time(12),
                ),
            )

    def test_weekday_out_of_range_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.validate(
                self.row(
                    7,
                    time(9),
                    time(12),
                )
            )

    def test_invalid_schedule_never_deletes_existing_records(self):
        organization = SimpleNamespace(pk=11)
        actor = object()

        def fake_hour(*, organization, **kwargs):
            row = self.row(**kwargs)
            row.organization = organization
            row.full_clean = Mock()
            return row

        hour_model = Mock(side_effect=fake_hour)

        with (
            patch.object(
                profile_details,
                "_ensure_profile_manager",
            ),
            patch.object(
                profile_details,
                "_record_change",
            ) as audit,
            patch.object(
                profile_details,
                "OrganizationBusinessHour",
                hour_model,
            ),
        ):
            with self.assertRaises(ValidationError):
                # Skip transaction.atomic to avoid database access.
                profile_details.replace_business_hours.__wrapped__(
                    organization=organization,
                    actor=actor,
                    validated_rows=[
                        {
                            "weekday": 0,
                            "opens_at": time(9),
                            "closes_at": time(13),
                        },
                        {
                            "weekday": 0,
                            "opens_at": time(12),
                            "closes_at": time(17),
                            "sort_order": 10,
                        },
                    ],
                )

            hour_model.objects.filter.assert_not_called()
            hour_model.objects.bulk_create.assert_not_called()
            audit.assert_not_called()

    def test_valid_schedule_is_validated_before_replacement(self):
        organization = SimpleNamespace(pk=11)
        events = []

        def fake_hour(*, organization, **kwargs):
            row = self.row(**kwargs)
            row.organization = organization
            row.full_clean = Mock(
                side_effect=lambda **_: events.append(
                    "validate"
                )
            )
            return row

        hour_model = Mock(side_effect=fake_hour)

        hour_model.objects.filter.return_value.delete.side_effect = (
            lambda: events.append("delete")
        )

        hour_model.objects.bulk_create.side_effect = (
            lambda rows: events.append("insert")
        )

        with (
            patch.object(
                profile_details,
                "_ensure_profile_manager",
            ),
            patch.object(
                profile_details,
                "_record_change",
            ) as audit,
            patch.object(
                profile_details,
                "OrganizationBusinessHour",
                hour_model,
            ),
        ):
            profile_details.replace_business_hours.__wrapped__(
                organization=organization,
                actor=object(),
                validated_rows=[
                    {
                        "weekday": 0,
                        "opens_at": time(9),
                        "closes_at": time(12),
                    },
                    {
                        "weekday": 0,
                        "opens_at": time(12),
                        "closes_at": time(15),
                        "sort_order": 10,
                    },
                ],
            )

            self.assertEqual(
                events,
                [
                    "validate",
                    "validate",
                    "delete",
                    "insert",
                ],
            )

            hour_model.objects.bulk_create.assert_called_once()
            audit.assert_called_once()
