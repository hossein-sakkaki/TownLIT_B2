# apps/accounts/management/commands/backfill_address_additional_encrypted.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Resumable Address.additional shadow backfill for a staged migration.

Run ONLY against the Stage A Address model (both legacy and encrypted columns).
Never run against the final encrypted-only model. No sensitive values are printed.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Address
from apps.core.crypto.field_protection import FieldProtectionError, FieldProtector


_FIELD = "accounts.Address.additional"


class Command(BaseCommand):
    help = (
        "Dry-run, backfill or verify Address.additional_encrypted. "
        "Production writes require --confirm-production-apply and an approved runbook."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verify-only", action="store_true")
        parser.add_argument("--confirm-production-apply", action="store_true")
        parser.add_argument("--after-id", type=int, default=0)
        parser.add_argument("--max-rows", type=int, default=None)
        parser.add_argument("--batch-size", type=int, default=200)

    def handle(self, *args, **options):
        apply = options["apply"]
        verify = options["verify_only"]
        confirmed = options["confirm_production_apply"]
        after_id = options["after_id"]
        max_rows = options["max_rows"]
        batch_size = options["batch_size"]

        if apply and verify:
            raise CommandError("--apply and --verify-only are mutually exclusive.")
        if confirmed and not apply:
            raise CommandError("--confirm-production-apply requires --apply.")
        if not settings.DEBUG and apply and not confirmed:
            raise CommandError("Production backfill requires --confirm-production-apply.")
        if after_id < 0 or max_rows is not None and max_rows < 1:
            raise CommandError("Invalid row range.")
        if not 1 <= batch_size <= 1000:
            raise CommandError("batch-size must be between 1 and 1000.")
        if verify and (after_id != 0 or max_rows is not None):
            raise CommandError("Full verification does not allow pagination filters.")

        try:
            protector = FieldProtector.from_environment()
        except FieldProtectionError as exc:
            raise CommandError("Address encryption keyring unavailable.") from exc

        counters = {"rows": 0, "verified": 0, "pending": 0,
                    "applied": 0, "conflicts": 0}
        last_id = after_id
        remaining = max_rows
        while True:
            limit = batch_size if remaining is None else min(batch_size, remaining)
            if limit <= 0:
                break
            ids = list(
                Address._base_manager.filter(pk__gt=last_id)
                .order_by("pk").values_list("pk", flat=True)[:limit]
            )
            if not ids:
                break
            for pk in ids:
                # Always load the current legacy value, not a stale snapshot.
                row = (Address._base_manager.only(
                    "pk", "additional", "additional_encrypted"
                ).get(pk=pk))
                counters["rows"] += 1
                if row.additional_encrypted is not None:
                    try:
                        decoded = protector.reveal(
                            row.additional_encrypted, field=_FIELD, row_id=row.pk
                        )
                    except FieldProtectionError as exc:
                        raise CommandError(
                            f"Unreadable encrypted Address record id={row.pk}."
                        ) from exc
                    if decoded != row.additional:
                        counters["conflicts"] += 1
                        raise CommandError(
                            f"Legacy/encrypted Address mismatch at id={row.pk}."
                        )
                    counters["verified"] += 1
                elif row.additional is None:
                    counters["verified"] += 1
                else:
                    counters["pending"] += 1
                    if apply:
                        ciphertext = protector.protect(
                            row.additional, field=_FIELD, row_id=row.pk
                        )
                        # CAS protects against concurrently changed legacy data.
                        updated = Address._base_manager.filter(
                            pk=row.pk,
                            additional=row.additional,
                            additional_encrypted__isnull=True,
                        ).update(additional_encrypted=ciphertext)
                        if updated == 1:
                            counters["applied"] += 1
                        else:
                            counters["conflicts"] += 1
                last_id = pk
            if remaining is not None:
                remaining -= len(ids)

        mode = "verify" if verify else "apply" if apply else "dry-run"
        self.stdout.write(
            " ".join(f"{k}={v}" for k, v in counters.items())
            + f" last_id={last_id} mode={mode}"
        )
        if counters["conflicts"]:
            raise CommandError("Concurrent changes or ciphertext mismatch; stop cutover.")
        if verify and counters["pending"]:
            raise CommandError("Backfill incomplete; plaintext column must remain.")
