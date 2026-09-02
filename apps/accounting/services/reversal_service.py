# apps/accounting/services/reversal_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounting.models import (
    JournalEntry,
    Transaction,
)

from .entry_number import generate_entry_number
from .period_service import assert_can_post_to_date


ZERO = Decimal("0.00")


class JournalEntryReversalError(Exception):
    """Raised when a journal reversal is not allowed."""

    pass


DOMAIN_MANAGED_SOURCES = {
    ("accounting", "pay_run"),
    ("accounting", "payroll_salary_payment"),
    ("accounting", "payroll_remittance"),
    ("accounting", "founder_loan"),
    ("accounting", "founder_repayment"),
}


def reverse_journal_entry(
    *,
    journal_entry: JournalEntry,
    reversal_date,
    reason: str,
    created_by=None,
    approved_by=None,
) -> JournalEntry:
    """Create an exact opposite posted entry."""

    reason = (reason or "").strip()

    if not reason:
        raise JournalEntryReversalError(
            "A reversal reason is required."
        )

    assert_can_post_to_date(reversal_date)

    with db_transaction.atomic():
        original = (
            JournalEntry.objects.select_for_update()
            .get(pk=journal_entry.pk)
        )

        if original.status != JournalEntry.STATUS_POSTED:
            raise JournalEntryReversalError(
                "Only posted journal entries can be reversed."
            )

        if original.reversal_of_id:
            raise JournalEntryReversalError(
                "A reversal entry cannot be reversed through "
                "the generic reversal service."
            )

        if original.reversed_at:
            raise JournalEntryReversalError(
                "This journal entry has already been reversed."
            )

        if JournalEntry.objects.filter(
            reversal_of=original,
        ).exists():
            raise JournalEntryReversalError(
                "A reversal already exists for this journal entry."
            )

        source_key = (
            original.source_app,
            original.source_model,
        )

        if source_key in DOMAIN_MANAGED_SOURCES:
            raise JournalEntryReversalError(
                "This journal entry belongs to a managed domain "
                "workflow and must be reversed by that domain service."
            )

        original_lines = list(
            Transaction.objects.select_for_update()
            .select_related(
                "account",
                "fund",
                "budget_line",
            )
            .filter(journal_entry=original)
            .order_by("line_number", "id")
        )

        if not original_lines:
            raise JournalEntryReversalError(
                "The original journal entry has no transaction lines."
            )

        total_debit = sum(
            (
                line.debit or ZERO
                for line in original_lines
            ),
            ZERO,
        )

        total_credit = sum(
            (
                line.credit or ZERO
                for line in original_lines
            ),
            ZERO,
        )

        if total_debit <= ZERO or total_debit != total_credit:
            raise JournalEntryReversalError(
                "The original journal entry is not balanced."
            )

        reversal = JournalEntry(
            entry_number=generate_entry_number(),
            entry_date=reversal_date,
            description=(
                f"Reversal of {original.entry_number} - "
                f"{original.description}"
            ),
            reference=original.reference,
            source_app="accounting",
            source_model="journal_reversal",
            source_ref=str(original.id),
            internal_note=reason,
            currency=original.currency,
            status=JournalEntry.STATUS_POSTED,
            posted_at=timezone.now(),
            created_by=created_by,
            approved_by=approved_by,
            reversal_of=original,
        )

        reversal._allow_posted_create = True
        reversal.save(force_insert=True)

        Transaction.objects.bulk_create(
            [
                Transaction(
                    journal_entry=reversal,
                    line_number=line.line_number,
                    account=line.account,
                    debit=line.credit,
                    credit=line.debit,
                    memo=(
                        f"Reversal of line {line.line_number}: "
                        f"{line.memo}"
                    ).strip(),
                    fund=line.fund,
                    budget_line=line.budget_line,
                    fund_code=line.fund_code,
                    budget_code=line.budget_code,
                )
                for line in original_lines
            ]
        )

        original.reversed_at = timezone.now()
        original.reversed_by = created_by
        original.reversal_reason = reason
        original.save(
            update_fields=[
                "reversed_at",
                "reversed_by",
                "reversal_reason",
                "updated_at",
            ]
        )

        from .workflow_service import mark_posted

        mark_posted(journal_entry=reversal)

        return reversal