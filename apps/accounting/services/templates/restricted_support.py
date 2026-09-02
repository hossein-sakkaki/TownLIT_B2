# apps/accounting/services/templates/restricted_support.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from decimal import Decimal

from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import (
    JournalEntryInput,
    JournalLineInput,
)


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
    """Record restricted support received."""

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
                    memo="Restricted support received in bank",
                    line_number=1,
                    fund_code=fund_code,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
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
    description: str,
    budget_code: str | None = None,
    budget_plan_code: str | None = None,
    budget_line_id: int | None = None,
    reference: str = "",
    source_app: str = "accounting",
    source_model: str = "restricted_expense",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record one restricted-fund expense."""

    amount = Decimal(
        str(amount)
    )

    budget_kwargs = {
        "budget_line_code": budget_code,
        "budget_plan_code": budget_plan_code,
        "budget_line_id": budget_line_id,
    }

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
                    debit=amount,
                    memo="Restricted expense",
                    line_number=1,
                    fund_code=fund_code,
                    **budget_kwargs,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    credit=amount,
                    memo="Paid from bank",
                    line_number=2,
                    fund_code=fund_code,
                    **budget_kwargs,
                ),
            ],
        )
    )