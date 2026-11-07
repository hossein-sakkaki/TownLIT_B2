# apps/accounts/management/commands/verify_user_privacy_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Verify encrypted-only Phase 4 fields without displaying or logging PII."""
from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from apps.core.crypto.field_protection import FieldProtector
from apps.core.crypto.protected_columns import reveal_column


_TARGETS = (
    ("accounts", "CustomUser", (("birthday", "birthday_encrypted", "date", False),)),
    ("accounts", "IdentityGrant", (("reason", "reason_encrypted", "text", True),)),
    ("accounts", "IdentityAuditLog", (
        ("reason", "reason_encrypted", "text", False),
        ("metadata", "metadata_encrypted", "json", False),
    )),
)


class Command(BaseCommand):
    help = "Validate ciphertext field binding and decoding for all Phase 4 rows."

    def handle(self, *args, **options):
        FieldProtector.from_environment()
        rows = 0
        encrypted_fields = 0
        errors = 0
        for app, model_name, fields in _TARGETS:
            Model = apps.get_model(app, model_name)
            for obj in Model._base_manager.order_by("pk").iterator(chunk_size=250):
                rows += 1
                for name, storage, kind, required in fields:
                    value = getattr(obj, storage)
                    if value is None:
                        if required:
                            errors += 1
                        continue
                    try:
                        reveal_column(obj, name, value, kind)
                        encrypted_fields += 1
                    except Exception:
                        errors += 1
        self.stdout.write(f"rows={rows} encrypted_fields={encrypted_fields} errors={errors}")
        if errors:
            raise CommandError("Protected field verification failed.")
