# apps/accounts/management/commands/backfill_townlit_verification.py

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.profiles.models import Member
from apps.accounts.services.townlit_engine import evaluate_and_apply_member_townlit_badge


class Command(BaseCommand):
    help = "Backfill TownLIT gold badge state for existing members."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of members to process per batch.",
        )

        parser.add_argument(
            "--member-id",
            type=int,
            help="Evaluate TownLIT gold badge for a single member only.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        member_id = options.get("member_id")

        processed = 0
        succeeded = 0
        failed = 0

        queryset = Member.objects.select_related("user").order_by("id")

        if member_id:
            queryset = queryset.filter(id=member_id)

        total = queryset.count()

        if total == 0:
            self.stdout.write(
                self.style.WARNING("No members found for TownLIT verification backfill.")
            )
            return

        self.stdout.write(
            self.style.NOTICE(
                f"Starting TownLIT verification backfill for {total} member(s)..."
            )
        )

        for member in queryset.iterator(chunk_size=batch_size):
            processed += 1

            try:
                with transaction.atomic():
                    state = evaluate_and_apply_member_townlit_badge(member)

                succeeded += 1

                self.stdout.write(
                    f"[{processed}/{total}] "
                    f"member_id={member.id} "
                    f"user_id={member.user_id} "
                    f"gold={state['is_townlit_verified']} "
                    f"score={state['score']} "
                    f"hard_ready={state['hard_requirements_ready']} "
                    f"score_ready={state['score_ready']} "
                    f"changed={state['changed']}"
                )

            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"[{processed}/{total}] member_id={member.id} failed: {exc}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"TownLIT verification backfill finished. "
                f"processed={processed}, succeeded={succeeded}, failed={failed}"
            )
        )


# docker compose exec backend python manage.py backfill_townlit_verification
# docker compose exec backend python manage.py backfill_townlit_verification --member-id 25
# docker compose exec backend python manage.py backfill_townlit_verification --batch-size 200