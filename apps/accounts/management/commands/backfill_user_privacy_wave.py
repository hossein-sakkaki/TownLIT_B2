# apps/accounts/management/commands/backfill_user_privacy_wave.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Development/staging/prod-runbook only: backfill and compare legacy fields.

Dry run is default. Does not print PII or encrypted blobs. Re-runnable.
"""
from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.crypto.field_protection import FieldProtector
from apps.core.crypto.protected_columns import protect_column, reveal_column


_TARGETS = (
    ("accounts", "CustomUser", (("birthday", "birthday_encrypted", "date"),)),
    ("accounts", "IdentityGrant", (("reason", "reason_encrypted", "text"),)),
    ("accounts", "IdentityAuditLog", (
        ("reason", "reason_encrypted", "text"),
        ("metadata", "metadata_encrypted", "json"),
    )),
)


class Command(BaseCommand):
    help = "Backfill the Phase 4 private fields. Dry-run by default; no sensitive output."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verify-only", action="store_true")
        parser.add_argument("--batch-size", type=int, default=250)

    def handle(self, *args, **options):
        if options["apply"] and options["verify_only"]:
            raise CommandError("Choose apply OR verify-only.")
        if options["batch_size"] < 1 or options["batch_size"] > 5000:
            raise CommandError("Batch size must be 1..5000.")
        FieldProtector.from_environment()  # fail closed before touching records
        total = {"rows": 0, "verified": 0, "pending": 0,
                 "applied": 0, "conflicts": 0}
        for app, model_name, fields in _TARGETS:
            Model = apps.get_model(app, model_name)
            ids = Model._base_manager.order_by("pk").values_list("pk", flat=True).iterator(
                chunk_size=options["batch_size"]
            )
            for pk in ids:
                if options["apply"]:
                    with transaction.atomic():
                        obj = Model._base_manager.select_for_update().get(pk=pk)
                        self._process(obj, fields, total, apply=True)
                else:
                    obj = Model._base_manager.get(pk=pk)
                    self._process(obj, fields, total, apply=False)
        mode = "apply" if options["apply"] else "verify" if options["verify_only"] else "dry-run"
        self.stdout.write(" ".join(f"{key}={value}" for key, value in total.items()) + f" mode={mode}")
        if total["conflicts"] or (options["verify_only"] and total["pending"]):
            raise CommandError("Protected field migration verification is incomplete.")

    @staticmethod
    def _process(obj, fields, counts, *, apply):
        counts["rows"] += 1
        for name, storage, kind in fields:
            original = getattr(obj, name)
            stored = getattr(obj, storage)
            if stored is None:
                if original is None:
                    counts["verified"] += 1
                    continue
                counts["pending"] += 1
                if apply:
                    value = protect_column(obj, name, original, kind)
                    type(obj)._base_manager.filter(pk=obj.pk).update(**{storage: value})
                    counts["applied"] += 1
                continue
            try:
                recovered = reveal_column(obj, name, stored, kind)
                if recovered == original:
                    counts["verified"] += 1
                else:
                    counts["conflicts"] += 1
            except Exception:  # no sensitive exception text
                counts["conflicts"] += 1
