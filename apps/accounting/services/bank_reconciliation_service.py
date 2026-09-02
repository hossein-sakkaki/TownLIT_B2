# apps/accounting/services/bank_reconciliation_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.accounting.models import (
    Account,
    BankReconciliationSession,
    BankStatementLine,
    JournalEntry,
    Transaction,
)


ZERO = Decimal("0.00")


class ReconciliationError(Exception):
    """Raised when reconciliation logic fails."""

    pass


def suggest_match_for_bank_line(
    *,
    bank_line: BankStatementLine,
    tolerance_days: int = 5,
):
    """Suggest one matching posted journal entry."""

    _assert_line_mutable(bank_line)

    if (
        bank_line.match_status
        == BankStatementLine.MATCH_IGNORED
    ):
        return None

    ledger_account = (
        bank_line.bank_account.ledger_account
    )

    amount_filter = _build_amount_filter(
        bank_line.amount
    )

    date_from = (
        bank_line.transaction_date
        - timedelta(days=tolerance_days)
    )

    date_to = (
        bank_line.transaction_date
        + timedelta(days=tolerance_days)
    )

    candidate_ids = list(
        Transaction.objects
        .filter(
            account=ledger_account,
            journal_entry__status=JournalEntry.STATUS_POSTED,
            journal_entry__entry_date__range=(
                date_from,
                date_to,
            ),
        )
        .filter(amount_filter)
        .values_list(
            "journal_entry_id",
            flat=True,
        )
        .distinct()[:2]
    )

    if len(candidate_ids) != 1:
        bank_line.match_status = (
            BankStatementLine.MATCH_UNMATCHED
        )
        bank_line.matched_journal_entry = None
        bank_line.save(
            update_fields=[
                "match_status",
                "matched_journal_entry",
            ]
        )
        return None

    entry = JournalEntry.objects.get(
        pk=candidate_ids[0]
    )

    bank_line.match_status = (
        BankStatementLine.MATCH_SUGGESTED
    )
    bank_line.matched_journal_entry = entry

    bank_line.save(
        update_fields=[
            "match_status",
            "matched_journal_entry",
        ]
    )

    return entry


def confirm_match(
    *,
    bank_line: BankStatementLine,
    journal_entry: JournalEntry,
    user,
):
    """Confirm a valid bank-to-ledger match."""

    with db_transaction.atomic():
        line = (
            BankStatementLine.objects
            .select_for_update()
            .select_related(
                "bank_account",
                "bank_account__ledger_account",
            )
            .get(pk=bank_line.pk)
        )

        _assert_line_mutable(line)

        if (
            line.match_status
            == BankStatementLine.MATCH_IGNORED
        ):
            raise ReconciliationError(
                "Ignored bank lines cannot be matched."
            )

        entry = JournalEntry.objects.get(
            pk=journal_entry.pk
        )

        if entry.status != JournalEntry.STATUS_POSTED:
            raise ReconciliationError(
                "Only posted journal entries can be matched."
            )

        matching_transaction_exists = (
            Transaction.objects
            .filter(
                journal_entry=entry,
                account=line.bank_account.ledger_account,
            )
            .filter(
                _build_amount_filter(
                    line.amount
                )
            )
            .exists()
        )

        if not matching_transaction_exists:
            raise ReconciliationError(
                "The selected journal entry does not contain "
                "the matching bank-account amount."
            )

        line.matched_journal_entry = entry
        line.match_status = (
            BankStatementLine.MATCH_MATCHED
        )
        line.matched_at = timezone.now()
        line.matched_by = user

        line.save(
            update_fields=[
                "matched_journal_entry",
                "match_status",
                "matched_at",
                "matched_by",
            ]
        )

        return line


def unmatch_bank_line(
    *,
    bank_line: BankStatementLine,
):
    """Return a bank line to unmatched state."""

    with db_transaction.atomic():
        line = (
            BankStatementLine.objects
            .select_for_update()
            .select_related("bank_account")
            .get(pk=bank_line.pk)
        )

        _assert_line_mutable(line)

        line.matched_journal_entry = None
        line.match_status = (
            BankStatementLine.MATCH_UNMATCHED
        )
        line.matched_at = None
        line.matched_by = None

        line.save(
            update_fields=[
                "matched_journal_entry",
                "match_status",
                "matched_at",
                "matched_by",
            ]
        )

        return line


def ignore_bank_line(
    *,
    bank_line: BankStatementLine,
    user,
    note: str = "",
):
    """Mark a bank line as intentionally ignored."""

    with db_transaction.atomic():
        line = (
            BankStatementLine.objects
            .select_for_update()
            .select_related("bank_account")
            .get(pk=bank_line.pk)
        )

        _assert_line_mutable(line)

        line.matched_journal_entry = None
        line.match_status = (
            BankStatementLine.MATCH_IGNORED
        )
        line.note = (
            note.strip()
            or line.note
        )
        line.matched_by = user
        line.matched_at = timezone.now()

        line.save(
            update_fields=[
                "matched_journal_entry",
                "match_status",
                "note",
                "matched_by",
                "matched_at",
            ]
        )

        return line


def calculate_ledger_ending_balance(
    *,
    bank_account,
    period_end,
):
    """Calculate balance only from posted ledger entries."""

    ledger_account = bank_account.ledger_account

    totals = Transaction.objects.filter(
        account=ledger_account,
        journal_entry__status=JournalEntry.STATUS_POSTED,
        journal_entry__entry_date__lte=period_end,
    ).aggregate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
    )

    total_debit = (
        totals["total_debit"]
        or ZERO
    )

    total_credit = (
        totals["total_credit"]
        or ZERO
    )

    if (
        ledger_account.normal_balance
        == Account.NORMAL_DEBIT
    ):
        return total_debit - total_credit

    return total_credit - total_debit


def refresh_reconciliation_session(
    *,
    session: BankReconciliationSession,
):
    """Refresh ledger balance and difference."""

    if (
        session.status
        == BankReconciliationSession.STATUS_LOCKED
    ):
        raise ReconciliationError(
            "Locked reconciliation sessions cannot be refreshed."
        )

    session.ledger_ending_balance = (
        calculate_ledger_ending_balance(
            bank_account=session.bank_account,
            period_end=session.period_end,
        )
    )

    session.unreconciled_difference = (
        session.statement_ending_balance
        - session.ledger_ending_balance
    )

    session.save(
        update_fields=[
            "ledger_ending_balance",
            "unreconciled_difference",
            "updated_at",
        ]
    )

    return session


def complete_reconciliation_session(
    *,
    session: BankReconciliationSession,
    user,
):
    """Complete only a fully reconciled session."""

    with db_transaction.atomic():
        locked = (
            BankReconciliationSession.objects
            .select_for_update()
            .select_related(
                "bank_account",
                "bank_account__ledger_account",
            )
            .get(pk=session.pk)
        )

        if (
            locked.status
            != BankReconciliationSession.STATUS_OPEN
        ):
            raise ReconciliationError(
                "Only open reconciliation sessions "
                "can be completed."
            )

        unmatched_exists = (
            BankStatementLine.objects
            .filter(
                bank_account=locked.bank_account,
                transaction_date__range=(
                    locked.period_start,
                    locked.period_end,
                ),
                match_status__in=[
                    BankStatementLine.MATCH_UNMATCHED,
                    BankStatementLine.MATCH_SUGGESTED,
                ],
            )
            .exists()
        )

        if unmatched_exists:
            raise ReconciliationError(
                "Cannot complete reconciliation while "
                "unmatched or suggested lines remain."
            )

        refresh_reconciliation_session(
            session=locked
        )

        if locked.unreconciled_difference != ZERO:
            raise ReconciliationError(
                "Cannot complete reconciliation with "
                f"a non-zero difference "
                f"({locked.unreconciled_difference})."
            )

        locked.status = (
            BankReconciliationSession.STATUS_COMPLETED
        )
        locked.completed_by = user
        locked.completed_at = timezone.now()

        locked.save(
            update_fields=[
                "status",
                "completed_by",
                "completed_at",
                "updated_at",
            ]
        )

        return locked


def lock_reconciliation_session(
    *,
    session: BankReconciliationSession,
    user,
):
    """Lock a completed reconciliation."""

    with db_transaction.atomic():
        locked = (
            BankReconciliationSession.objects
            .select_for_update()
            .select_related(
                "bank_account",
                "bank_account__ledger_account",
            )
            .get(pk=session.pk)
        )

        if (
            locked.status
            != BankReconciliationSession.STATUS_COMPLETED
        ):
            raise ReconciliationError(
                "Only completed reconciliation sessions "
                "can be locked."
            )

        refresh_reconciliation_session(
            session=locked
        )

        if locked.unreconciled_difference != ZERO:
            raise ReconciliationError(
                "A reconciliation with non-zero difference "
                "cannot be locked."
            )

        locked.status = (
            BankReconciliationSession.STATUS_LOCKED
        )
        locked.locked_by = user
        locked.locked_at = timezone.now()

        locked.save(
            update_fields=[
                "status",
                "locked_by",
                "locked_at",
                "updated_at",
            ]
        )

        return locked


def _build_amount_filter(
    amount: Decimal,
) -> Q:
    """Build the ledger-side bank amount filter."""

    if amount > ZERO:
        return Q(
            debit=amount,
            credit=ZERO,
        )

    if amount < ZERO:
        return Q(
            credit=abs(amount),
            debit=ZERO,
        )

    raise ReconciliationError(
        "Zero-value bank lines cannot be matched."
    )


def _assert_line_mutable(
    bank_line: BankStatementLine,
) -> None:
    """Protect completed reconciliation periods."""

    protected = (
        BankReconciliationSession.objects
        .filter(
            bank_account=bank_line.bank_account,
            period_start__lte=bank_line.transaction_date,
            period_end__gte=bank_line.transaction_date,
            status__in=[
                BankReconciliationSession.STATUS_COMPLETED,
                BankReconciliationSession.STATUS_LOCKED,
            ],
        )
        .exists()
    )

    if protected:
        raise ReconciliationError(
            "This bank line belongs to a completed "
            "or locked reconciliation period."
        )