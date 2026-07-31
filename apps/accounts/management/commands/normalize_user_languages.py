#
#  apps/accounts/management/commands/normalize_user_languages.py
#  TownLIT
#
#  Created by Hossein Sakkaki on 2026-07-30.
#  Last Update by Hossein Sakkaki on 2026-07-30.
#


from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, Q


CustomUser = get_user_model()


class Command(BaseCommand):
    help = (
        "Normalize user profile languages before applying "
        "the distinct-language database constraint."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the changes and roll them back.",
        )

        parser.add_argument(
            "--mark-completed",
            action="store_true",
            help=(
                "Mark all existing users as having completed "
                "language onboarding."
            ),
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        mark_completed = bool(options["mark_completed"])

        with transaction.atomic():
            blank_primary_count = (
                CustomUser.objects
                .filter(primary_language="")
                .update(primary_language=None)
            )

            blank_secondary_count = (
                CustomUser.objects
                .filter(secondary_language="")
                .update(secondary_language=None)
            )

            promoted_secondary_count = (
                CustomUser.objects
                .filter(
                    primary_language__isnull=True,
                    secondary_language__isnull=False,
                )
                .update(
                    primary_language=F("secondary_language"),
                    secondary_language=None,
                )
            )

            duplicate_secondary_count = (
                CustomUser.objects
                .filter(
                    primary_language__isnull=False,
                    secondary_language__isnull=False,
                    primary_language=F("secondary_language"),
                )
                .update(
                    secondary_language=None,
                )
            )

            defaulted_english_count = (
                CustomUser.objects
                .filter(
                    primary_language__isnull=True,
                    secondary_language__isnull=True,
                )
                .update(
                    primary_language="en",
                )
            )

            completed_count = 0

            if mark_completed:
                completed_count = (
                    CustomUser.objects
                    .filter(language_onboarding_completed=False)
                    .update(language_onboarding_completed=True)
                )

            remaining_invalid_count = (
                CustomUser.objects
                .filter(
                    Q(primary_language="")
                    | Q(secondary_language="")
                    | Q(
                        primary_language__isnull=True,
                        secondary_language__isnull=False,
                    )
                    | Q(
                        primary_language__isnull=False,
                        secondary_language__isnull=False,
                        primary_language=F("secondary_language"),
                    )
                )
                .count()
            )

            summary = {
                "blank_primary_normalized": blank_primary_count,
                "blank_secondary_normalized": blank_secondary_count,
                "secondary_promoted_to_primary": promoted_secondary_count,
                "duplicate_secondary_removed": duplicate_secondary_count,
                "missing_languages_defaulted_to_english": defaulted_english_count,
                "language_onboarding_marked_completed": completed_count,
                "remaining_invalid_rows": remaining_invalid_count,
                "dry_run": dry_run,
            }

            for key, value in summary.items():
                self.stdout.write(f"{key}: {value}")

            if remaining_invalid_count:
                raise RuntimeError(
                    "Language normalization left invalid user rows."
                )

            if dry_run:
                transaction.set_rollback(True)

                self.stdout.write(
                    self.style.WARNING(
                        "Dry run completed. All changes were rolled back."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        "User languages normalized successfully."
                    )
                )
                

# sudo docker compose exec backend python manage.py normalize_user_languages \
#     --dry-run \
#     --mark-completed
    

# sudo docker compose exec backend python manage.py normalize_user_languages --mark-completed