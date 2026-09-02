# apps/accounting/services/historical_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from apps.accounting.services.posting_engine import (
    post_journal_entry,
)
from apps.accounting.services.schemas import (
    JournalEntryInput,
    JournalLineInput,
)


class HistoricalAccountingError(Exception):
    """Raised when historical posting input is invalid."""

    pass


def post_historical_journal(
    *,
    entry_date,
    description: str,
    lines: list[JournalLineInput],
    batch_ref: str,
    reference: str = "",
    internal_note: str = "",
    created_by=None,
    approved_by=None,
):
    """Post one idempotent historical journal entry."""

    batch_ref = (
        batch_ref or ""
    ).strip()

    if not batch_ref:
        raise HistoricalAccountingError(
            "batch_ref is required."
        )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="historical_import",
            source_ref=f"historical:{batch_ref}",
            internal_note=internal_note,
            created_by=created_by,
            approved_by=approved_by,
            lines=list(lines),
        )
    )


def post_opening_balance(
    *,
    entry_date,
    description: str,
    lines: list[JournalLineInput],
    batch_ref: str,
    reference: str = "",
    internal_note: str = "",
    created_by=None,
    approved_by=None,
):
    """Post one balanced opening-balance journal."""

    batch_ref = (
        batch_ref or ""
    ).strip()

    if not batch_ref:
        raise HistoricalAccountingError(
            "batch_ref is required."
        )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="opening_balance",
            source_ref=f"opening:{batch_ref}",
            internal_note=(
                internal_note
                or "Historical opening balance"
            ),
            created_by=created_by,
            approved_by=approved_by,
            lines=list(lines),
        )
    )