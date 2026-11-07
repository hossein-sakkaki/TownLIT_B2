# apps/accounts/management/commands/backfill_identity_private_fields.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Safe resumable shadow backfill of two IdentityVerification fields."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models.identity import IdentityVerification
from apps.accounts.services.identity_private_fields import (
    decrypt_identity_field,
    encrypt_identity_field,
)


class Command(BaseCommand):
    help = "Dry-run by default; --apply updates only new encrypted shadow columns."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verify-only", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)

    def handle(self, *args, **options):
        if options["apply"] and options["verify_only"]:
            raise CommandError("Choose only one operation mode.")
        if options["batch_size"] < 1 or options["batch_size"] > 1000:
            raise CommandError("batch-size must be between 1 and 1000.")

        counts = dict(rows=0, verified=0, pending=0, applied=0, conflicts=0)
        last_pk = 0
        batch_size = options["batch_size"]
        while True:
            ids = list(
                IdentityVerification.objects.filter(pk__gt=last_pk)
                .order_by("pk").values_list("pk", flat=True)[:batch_size]
            )
            if not ids:
                break
            for pk in ids:
                # Keep each row's comparison and optional update atomic.
                try:
                    with transaction.atomic():
                        row = IdentityVerification.objects.select_for_update().get(pk=pk)
                        counts["rows"] += 1
                        updates = {}
                        row_pending = False
                        row_conflict = False
                        for name in ("provider_payload", "notes"):
                            original = getattr(row, name)
                            ciphertext = getattr(row, f"{name}_encrypted")
                            if ciphertext is None:
                                if original is not None:
                                    row_pending = True
                                    if options["apply"]:
                                        updates[f"{name}_encrypted"] = encrypt_identity_field(name, original, row.user_id)
                            else:
                                decoded = decrypt_identity_field(name, ciphertext, row.user_id)
                                if decoded != original:
                                    row_conflict = True
                        if row_conflict:
                            counts["conflicts"] += 1
                        elif row_pending:
                            counts["pending"] += 1
                            if updates and options["apply"]:
                                IdentityVerification.objects.filter(pk=pk).update(**updates)
                                counts["applied"] += 1
                        else:
                            counts["verified"] += 1
                except Exception as exc:
                    raise CommandError(f"Identity field validation failed at record id={pk}; values omitted.") from exc
            last_pk = ids[-1]
        self.stdout.write(
            " ".join(f"{k}={v}" for k, v in counts.items())
            + f" mode={'apply' if options['apply'] else 'verify' if options['verify_only'] else 'dry-run'}"
        )
        if counts["conflicts"]:
            raise CommandError("Identity private-field conflicts detected; cutover prohibited.")
        if options["verify_only"] and counts["pending"]:
            raise CommandError("Identity private-field backfill is incomplete.")
