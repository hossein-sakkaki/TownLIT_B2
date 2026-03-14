# apps/accounts/management/commands/backfill_trust_scores.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.services.trust_score import update_user_trust_score

User = get_user_model()


class Command(BaseCommand):
    help = "Backfill trust scores for existing users."

    def add_arguments(self, parser):
        # Optional batch size
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of users to process per batch.",
        )

        # Optional single user mode
        parser.add_argument(
            "--user-id",
            type=int,
            help="Recalculate trust score for a single user only.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        user_id = options.get("user_id")

        processed = 0
        succeeded = 0
        failed = 0

        queryset = User.objects.all().order_by("id")

        if user_id:
            queryset = queryset.filter(id=user_id)

        total = queryset.count()

        if total == 0:
            self.stdout.write(
                self.style.WARNING("No users found for trust backfill.")
            )
            return

        self.stdout.write(
            self.style.NOTICE(f"Starting trust score backfill for {total} user(s)...")
        )

        for user in queryset.iterator(chunk_size=batch_size):
            processed += 1

            try:
                with transaction.atomic():
                    trust = update_user_trust_score(user)

                succeeded += 1

                self.stdout.write(
                    f"[{processed}/{total}] user_id={user.id} score={trust.score} eligible={trust.eligible_for_verification}"
                )

            except Exception as exc:
                failed += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"[{processed}/{total}] user_id={user.id} failed: {exc}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Trust score backfill finished. processed={processed}, succeeded={succeeded}, failed={failed}"
            )
        )


# docker compose exec backend python manage.py backfill_trust_scores
# docker compose exec backend python manage.py backfill_trust_scores --user-id 25
# docker compose exec backend python manage.py backfill_trust_scores --batch-size 200 