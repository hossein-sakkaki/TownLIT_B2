# apps/accounting/management/commands/sync_payroll_salary_payments.py

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.accounting.models import JournalEntry, PayStub


class Command(BaseCommand):
    help = "Link existing salary payment journal entries to pay stubs."

    def handle(self, *args, **options):
        linked = 0

        stubs = PayStub.objects.filter(
            actual_paid__gt=0,
            salary_payment_journal_entry__isnull=True,
        ).select_related("employee", "pay_run")

        for stub in stubs:
            entry = (
                JournalEntry.objects.filter(
                    source_app="accounting",
                    source_model="pay_stub_payment",
                    status=JournalEntry.STATUS_POSTED,
                )
                .filter(
                    Q(source_ref=f"pay_stub_salary_payment:{stub.id}")
                    | Q(source_ref__startswith=f"{stub.id}-")
                )
                .order_by("entry_date", "id")
                .first()
            )

            if not entry:
                continue

            stub.salary_payment_journal_entry = entry
            stub.salary_payment_amount = stub.actual_paid
            stub.salary_paid_on = entry.entry_date
            stub.salary_payment_reference = entry.reference
            stub.save(
                update_fields=[
                    "salary_payment_journal_entry",
                    "salary_payment_amount",
                    "salary_paid_on",
                    "salary_payment_reference",
                    "updated_at",
                ]
            )

            linked += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"{linked} salary payment journal entry/entries linked."
            )
        )
        
        
# docker compose exec backend python manage.py sync_payroll_salary_payments