# apps/accounts/management/commands/backfill_contact_protection.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Idempotent legacy contact snapshot backfill. Never print contact values."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from apps.core.crypto.blind_index import BlindIndexer
from apps.core.crypto.field_protection import FieldProtector
from apps.accounts.services.contact_protection import (
    blind_index, encrypt_contact, decrypt_contact, index_matches,
)

FIELDS = (
    ("email", "email_encrypted", "email_blind_index"),
    ("mobile_number", "mobile_number_encrypted", "mobile_number_blind_index"),
)


class Command(BaseCommand):
    help = "Backfill encrypted contact shadows and blind indexes. --verify-only compares stored values."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--verify-only", action="store_true")

    def handle(self, *args, **options):
        if options["apply"] and options["verify_only"]:
            raise CommandError("Choose either --apply or --verify-only.")
        FieldProtector.from_environment()
        BlindIndexer.from_environment()
        User = get_user_model()
        rows = pending = verified = applied = conflicts = 0
        ids = User._base_manager.order_by("pk").values_list("pk", flat=True).iterator(chunk_size=250)
        for pk in ids:
            rows += 1
            try:
                with transaction.atomic():
                    user = User._base_manager.select_for_update().get(pk=pk)
                    changes = {}
                    has_conflict = False
                    for name, storage, index_storage in FIELDS:
                        plain = getattr(user, name)
                        ciphertext = getattr(user, storage)
                        idx = getattr(user, index_storage)
                        # Treat both None and blank as absent for email lookup,
                        # while preserving text representation in encryption.
                        expected_idx = blind_index(plain, field=name)
                        if plain is None and ciphertext is None and idx is None:
                            verified += 1
                            continue
                        if ciphertext is not None:
                            try:
                                recovered = decrypt_contact(user, ciphertext, field=name)
                            except Exception:
                                has_conflict = True
                                continue
                            if recovered != plain:
                                has_conflict = True
                                continue
                        if idx is not None and not index_matches(idx, plain, field=name):
                            has_conflict = True
                            continue
                        if ciphertext is None or idx != expected_idx:
                            pending += 1
                            if ciphertext is None:
                                changes[storage] = encrypt_contact(user, plain, field=name)
                            if idx is None or idx != expected_idx:
                                changes[index_storage] = expected_idx
                        else:
                            verified += 1
                    if has_conflict:
                        conflicts += 1
                        continue
                    if changes and options["apply"]:
                        User._base_manager.filter(pk=pk).update(**changes)
                        applied += 1
            except IntegrityError:
                conflicts += 1
            except Exception:
                conflicts += 1
        mode = "verify" if options["verify_only"] else "apply" if options["apply"] else "dry-run"
        self.stdout.write(
            f"rows={rows} verified={verified} pending={pending} "
            f"applied={applied} conflicts={conflicts} mode={mode}"
        )
        if conflicts or (options["verify_only"] and pending):
            raise CommandError("Contact backfill verification failed. No legacy columns may be dropped.")
