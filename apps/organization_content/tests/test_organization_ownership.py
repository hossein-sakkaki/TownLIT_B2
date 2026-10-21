# apps/organization_content/tests/test_organization_ownership.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework import serializers

from apps.sanctuary.services import ownership, target_access


class OrganizationOwnershipTests(SimpleTestCase):
    def target(self):
        class Target:
            _meta = SimpleNamespace(app_label="organization_content", model_name="organizationupdate",
                                    label_lower="organization_content.organizationupdate")
        target = Target()
        target.organization = object()
        target.created_by = SimpleNamespace(id=91, pk=91)
        target.is_active = True
        target.is_suspended = False
        target.is_available = lambda: True
        return target

    def test_sanctuary_uses_current_organization_managers(self):
        target = self.target()
        with patch.object(ownership, "effective_organization_manager_user_ids", return_value={7, 11}) as managers:
            ownership.register_default_resolvers()
            self.assertEqual(ownership.get_owner_user_ids(target), {7, 11})
            managers.assert_called_once_with(organization=target.organization)

    def test_operator_is_not_the_personal_owner_of_the_post(self):
        self.assertIsNone(target_access.resolve_target_owner_user_id(self.target()))

    def test_manager_cannot_report_own_organization_content(self):
        user = SimpleNamespace(pk=7, id=7, is_authenticated=True)
        with patch.object(ownership, "get_owner_user_ids", return_value={7, 11}):
            with self.assertRaises(serializers.ValidationError):
                target_access._validate_content_target(user=user, target=self.target())
