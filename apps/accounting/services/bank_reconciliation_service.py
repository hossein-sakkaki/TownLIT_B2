# apps/accounting/services/bank_reconciliation_service.py

from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum, Q
from django.utils import timezone

from apps.accounting.models import (
    BankAccount,
    BankStatementLine,
    BankReconciliationSession,
    JournalEntry,
    Transaction,
    Account,
)


ZERO = Decimal("0.00")


class ReconciliationError(Exception):
    """Raised when reconciliation logic fails."""
    pass


def suggest_match_for_bank_line(*, bank_line: BankStatementLine, tolerance_days: int = 5):
    """
    Suggest one matching journal entry using bank ledger account,
    amount, and nearby date.
    """

    bank_account = bank_line.bank_account
    ledger_account = bank_account.ledger_account

    # Positive bank inflow -> debit bank
    # Negative bank outflow -> credit bank
    if bank_line.amount > 0:
        amount_filter = Q(debit=bank_line.amount, credit=0)
    else:
        amount_filter = Q(credit=abs(bank_line.amount), debit=0)

    date_from = bank_line.transaction_date - timedelta(days=tolerance_days)
    date_to = bank_line.transaction_date + timedelta(days=tolerance_days)

    candidates = (
        Transaction.objects.select_related("journal_entry", "account")
        .filter(
            account=ledger_account,
            journal_entry__status=JournalEntry.STATUS_POSTED,
            journal_entry__entry_date__range=(date_from, date_to),
        )
        .filter(amount_filter)
        .order_by("journal_entry__entry_date", "journal_entry__id")
    )

    if not candidates.exists():
        bank_line.match_status = BankStatementLine.MATCH_UNMATCHED
        bank_line.save(update_fields=["match_status"])
        return None

    if candidates.count() == 1:
        bank_line.match_status = BankStatementLine.MATCH_SUGGESTED
        bank_line.matched_journal_entry = candidates.first().journal_entry
        bank_line.save(update_fields=["match_status", "matched_journal_entry"])
        return candidates.first().journal_entry

    bank_line.match_status = BankStatementLine.MATCH_UNMATCHED
    bank_line.save(update_fields=["match_status"])
    return None


def confirm_match(*, bank_line: BankStatementLine, journal_entry: JournalEntry, user):
    """
    Confirm a reconciliation match.
    """

    if bank_line.match_status == BankStatementLine.MATCH_IGNORED:
        raise ReconciliationError("Ignored bank lines cannot be matched.")

    bank_line.matched_journal_entry = journal_entry
    bank_line.match_status = BankStatementLine.MATCH_MATCHED
    bank_line.matched_at = timezone.now()
    bank_line.matched_by = user
    bank_line.save(
        update_fields=[
            "matched_journal_entry",
            "match_status",
            "matched_at",
            "matched_by",
        ]
    )

    return bank_line


def ignore_bank_line(*, bank_line: BankStatementLine, user, note: str = ""):
    """
    Mark a bank line as ignored.
    """

    bank_line.match_status = BankStatementLine.MATCH_IGNORED
    bank_line.note = note.strip() or bank_line.note
    bank_line.matched_by = user
    bank_line.matched_at = timezone.now()
    bank_line.save(
        update_fields=[
            "match_status",
            "note",
            "matched_by",
            "matched_at",
        ]
    )
    return bank_line


def calculate_ledger_ending_balance(*, bank_account: BankAccount, period_end):
    """
    Calculate ledger ending balance for the linked bank ledger account.
    """

    ledger_account = bank_account.ledger_account
    qs = Transaction.objects.filter(
        account=ledger_account,
        journal_entry__status=JournalEntry.STATUS_POSTED,
        journal_entry__entry_date__lte=period_end,
    )

    total_debit = qs.aggregate(v=Sum("debit"))["v"] or ZERO
    total_credit = qs.aggregate(v=Sum("credit"))["v"] or ZERO

    if ledger_account.normal_balance == Account.NORMAL_DEBIT:
        return bank_account.opening_balance + total_debit - total_credit

    return bank_account.opening_balance + total_credit - total_debit


def refresh_reconciliation_session(*, session: BankReconciliationSession):
    """
    Refresh balances and difference for a reconciliation session.
    """

    session.ledger_ending_balance = calculate_ledger_ending_balance(
        bank_account=session.bank_account,
        period_end=session.period_end,
    )

    session.unreconciled_difference = session.statement_ending_balance - session.ledger_ending_balance
    session.save(
        update_fields=[
            "ledger_ending_balance",
            "unreconciled_difference",
            "updated_at",
        ]
    )
    return session


def complete_reconciliation_session(*, session: BankReconciliationSession, user):
    """
    Complete reconciliation only if no unmatched lines remain for the period.
    """

    unmatched_exists = BankStatementLine.objects.filter(
        bank_account=session.bank_account,
        transaction_date__range=(session.period_start, session.period_end),
        match_status__in=[
            BankStatementLine.MATCH_UNMATCHED,
            BankStatementLine.MATCH_SUGGESTED,
        ],
    ).exists()

    if unmatched_exists:
        raise ReconciliationError(
            "Cannot complete reconciliation while unmatched or suggested lines remain."
        )

    refresh_reconciliation_session(session=session)

    session.status = BankReconciliationSession.STATUS_COMPLETED
    session.completed_by = user
    session.completed_at = timezone.now()
    session.save(
        update_fields=[
            "status",
            "completed_by",
            "completed_at",
            "updated_at",
        ]
    )
    return session