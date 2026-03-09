# apps/accounting/services/templates/grants.py

from datetime import date
from decimal import Decimal

from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from apps.accounting.services.account_lookup import AccountCodes


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
):
    """
    Record grant cash received.
    grant_type: government | foundation | church
    """

    revenue_code_map = {
        "government": AccountCodes.GOVERNMENT_GRANTS,
        "foundation": AccountCodes.FOUNDATION_GRANTS,
        "church": AccountCodes.CHURCH_GRANTS,
    }

    revenue_account_code = revenue_code_map.get(grant_type, AccountCodes.GRANTS)

    return post_journal_entry(
        JournalEntryInput(
            date=entry_date,
            description=description,
            reference=reference,
            source_app=source_app,
            source_model=source_model,
            source_ref=source_ref,
            lines=[
                JournalLineInput(
                    account_code=bank_account_code,
                    debit=Decimal(amount),
                    memo="Grant cash received",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Grant income recognized",
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
):
    """
    Record an approved grant receivable before cash arrives.
    """

    revenue_code_map = {
        "government": AccountCodes.GOVERNMENT_GRANTS,
        "foundation": AccountCodes.FOUNDATION_GRANTS,
        "church": AccountCodes.CHURCH_GRANTS,
    }

    revenue_account_code = revenue_code_map.get(grant_type, AccountCodes.GRANTS)

    return post_journal_entry(
        JournalEntryInput(
            date=entry_date,
            description=description,
            reference=reference,
            source_app=source_app,
            source_model=source_model,
            source_ref=source_ref,
            lines=[
                JournalLineInput(
                    account_code=receivable_account_code,
                    debit=Decimal(amount),
                    memo="Grant receivable recognized",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Grant income recognized",
                ),
            ],
        )
    )