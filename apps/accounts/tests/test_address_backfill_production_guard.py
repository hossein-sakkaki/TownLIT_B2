# apps/accounts/tests/test_address_backfill_production_guard.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Safety guard tests for the STAGING Stage A Address backfill command."""

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class AddressBackfillProductionGuardTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_apply_without_explicit_production_authorization_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "--confirm-production-apply"):
            call_command("backfill_address_additional_encrypted", apply=True)

    @override_settings(DEBUG=False)
    def test_confirmation_without_apply_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "requires --apply"):
            call_command("backfill_address_additional_encrypted", confirm_production_apply=True)

    @override_settings(DEBUG=False)
    def test_partial_full_verify_is_rejected(self):
        with self.assertRaisesMessage(CommandError, "does not allow pagination"):
            call_command("backfill_address_additional_encrypted", verify_only=True, after_id=1)
