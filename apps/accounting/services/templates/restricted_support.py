# apps/accounting/services/templates/restricted_support.py

from decimal import Decimal

from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from apps.accounting.services.account_lookup import AccountCodes


def record_restricted_support_received(
    *,
    entry_date,
    amount: Decimal,
    revenue_account_code: str,
    fund_code: str,
    description: str,
    reference: str = "",
    source_app: str = "advancement",
    source_model: str = "support",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """
    Record restricted support received into bank and tag it to a fund.
    """

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
                    debit=Decimal(amount),
                    memo="Restricted support received in bank",
                    line_number=1,
                    fund_code=fund_code,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Restricted support recognized",
                    line_number=2,
                    fund_code=fund_code,
                ),
            ],
        )
    )


def record_restricted_expense(
    *,
    entry_date,
    amount: Decimal,
    expense_account_code: str,
    fund_code: str,
    budget_code: str | None,
    description: str,
    reference: str = "",
    source_app: str = "accounting",
    source_model: str = "restricted_expense",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """
    Record an expense charged to a specific restricted fund/budget line.
    """

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
                    account_code=expense_account_code,
                    debit=Decimal(amount),
                    memo="Restricted expense",
                    line_number=1,
                    fund_code=fund_code,
                    budget_code=budget_code,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    credit=Decimal(amount),
                    memo="Paid from bank",
                    line_number=2,
                    fund_code=fund_code,
                    budget_code=budget_code,
                ),
            ],
        )
    )