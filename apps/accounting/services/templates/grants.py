# apps/accounting/services/templates/grants.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from datetime import date
from decimal import Decimal

from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import (
    JournalEntryInput,
    JournalLineInput,
)


def record_grant_received(
    *,
    entry_date: date,
    amount: Decimal,
    grant_type: str,
    description: str,
    reference: str = "",
    source_app: str = "advancement",
    source_model: str = "grant_disbursement",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record received grant cash."""

    revenue_code_map = {
        "government": AccountCodes.GOVERNMENT_GRANTS,
        "foundation": AccountCodes.FOUNDATION_GRANTS,
        "church": AccountCodes.CHURCH_GRANTS,
    }

    revenue_account_code = revenue_code_map.get(
        grant_type,
        AccountCodes.GRANTS,
    )

    amount = Decimal(
        str(amount)
    )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app=source_app,
            source_model=source_model,
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=bank_account_code,
                    debit=amount,
                    memo="Grant cash received",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Grant income recognized",
                    line_number=2,
                ),
            ],
        )
    )


def record_grant_receivable(
    *,
    entry_date: date,
    amount: Decimal,
    grant_type: str,
    description: str,
    reference: str = "",
    source_app: str = "advancement",
    source_model: str = "grant_award",
    source_ref: str = "",
    receivable_account_code: str = AccountCodes.GRANTS_RECEIVABLE,
    created_by=None,
    approved_by=None,
):
    """Record approved grant receivable."""

    revenue_code_map = {
        "government": AccountCodes.GOVERNMENT_GRANTS,
        "foundation": AccountCodes.FOUNDATION_GRANTS,
        "church": AccountCodes.CHURCH_GRANTS,
    }

    revenue_account_code = revenue_code_map.get(
        grant_type,
        AccountCodes.GRANTS,
    )

    amount = Decimal(
        str(amount)
    )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app=source_app,
            source_model=source_model,
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=receivable_account_code,
                    debit=amount,
                    memo="Grant receivable recognized",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Grant income recognized",
                    line_number=2,
                ),
            ],
        )
    )