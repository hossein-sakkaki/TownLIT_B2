# apps/accounts/management/commands/verify_email_cutover_readiness.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Read-only verification of User email ciphertext, blind index and username.

This validates protected data integrity. Deployment authorization requires
a separate, confirmed production migration runbook.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.services.contact_protection import decrypt_contact, index_matches
from apps.accounts.services.email_lookup import user_email_index
from apps.core.crypto.blind_index import BlindIndexer
from apps.core.crypto.field_protection import FieldProtector


class Command(BaseCommand):
    help = "Verify read-only email shadow/index readiness; never authorizes DB column removal."

    def handle(self, *args, **options):
        FieldProtector.from_environment()
        BlindIndexer.from_environment()
        User = get_user_model()
        rows = verified = errors = missing_username = 0
        for user in User._base_manager.order_by("pk").iterator(chunk_size=250):
            rows += 1
            username = getattr(user, "username", None)
            if not isinstance(username, str) or not username.strip():
                missing_username += 1
                errors += 1
            try:
                email = user.email
                if not isinstance(email, str) or not email.strip():
                    errors += 1
                    continue
                if not user.email_encrypted or not user.email_blind_index:
                    errors += 1
                    continue
                if decrypt_contact(user, user.email_encrypted, field="email") != email:
                    errors += 1
                    continue
                if not index_matches(user.email_blind_index, email, field="email"):
                    errors += 1
                    continue
                # The stored index MUST match the active key before cutover.
                # Old-key indexes may validate cryptographically but cannot be
                # resolved by current unique-email lookups.
                if user.email_blind_index != user_email_index(email):
                    errors += 1
                    continue
                verified += 1
            except Exception:
                errors += 1
        self.stdout.write(
            f"rows={rows} email_verified={verified} "
            f"missing_username={missing_username} errors={errors}"
        )
        concrete_email = any(
            field.name == "email" for field in User._meta.concrete_fields
        )
        self.stdout.write(
            "email_storage=" + ("legacy_plaintext" if concrete_email else "encrypted_only")
        )
        if errors:
            raise CommandError("Email shadow/index readiness verification failed.")
