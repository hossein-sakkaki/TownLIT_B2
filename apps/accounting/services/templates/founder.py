# apps/accounting/services/templates/founder.py
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


def record_founder_loan(
    *,
    entry_date,
    amount: Decimal,
    expense_account_code: str,
    description: str,
    reference: str = "",
    source_ref: str = "",
    founder_liability_code: str = AccountCodes.LOAN_FROM_HOSSEIN,
    memo_expense: str = "",
    memo_liability: str = "",
    created_by=None,
    approved_by=None,
):
    """Record an expense personally funded by the founder."""

    amount = Decimal(
        str(amount)
    )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="founder_loan",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=expense_account_code,
                    debit=amount,
                    memo=memo_expense or "Expense paid by founder",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=founder_liability_code,
                    credit=amount,
                    memo=memo_liability or "Amount owed to founder",
                    line_number=2,
                ),
            ],
        )
    )


def record_founder_repayment(
    *,
    entry_date: date,
    amount: Decimal,
    description: str,
    reference: str = "",
    source_ref: str = "",
    founder_liability_code: str = AccountCodes.LOAN_FROM_HOSSEIN,
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record founder-loan repayment."""

    amount = Decimal(
        str(amount)
    )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="founder_repayment",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=founder_liability_code,
                    debit=amount,
                    memo="Founder loan reduced",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    credit=amount,
                    memo="Paid from TownLIT bank",
                    line_number=2,
                ),
            ],
        )
    )


def record_founder_withdrawal(
    *,
    entry_date: date,
    amount: Decimal,
    description: str,
    reference: str = "",
    source_ref: str = "",
    withdrawal_account_code: str = AccountCodes.FOUNDER_WITHDRAWALS,
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record founder personal withdrawal."""

    amount = Decimal(
        str(amount)
    )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="founder_withdrawal",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=withdrawal_account_code,
                    debit=amount,
                    memo="Founder personal withdrawal",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    credit=amount,
                    memo="Paid from TownLIT bank",
                    line_number=2,
                ),
            ],
        )
    )


def record_home_office_allocation(
    *,
    entry_date: date,
    total_paid: Decimal,
    business_share: Decimal,
    personal_share: Decimal,
    description: str,
    reference: str = "",
    source_ref: str = "",
    expense_account_code: str = AccountCodes.HOME_OFFICE_EXPENSE,
    withdrawal_account_code: str = AccountCodes.FOUNDER_WITHDRAWALS,
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record mixed business/personal home-office payment."""

    total_paid = Decimal(
        str(total_paid)
    )

    business_share = Decimal(
        str(business_share)
    )

    personal_share = Decimal(
        str(personal_share)
    )

    if business_share + personal_share != total_paid:
        raise ValueError(
            "Business share + personal share must equal total paid."
        )

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description,
            reference=reference,
            source_app="accounting",
            source_model="home_office_allocation",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=approved_by,
            lines=[
                JournalLineInput(
                    account_code=expense_account_code,
                    debit=business_share,
                    memo="TownLIT share of home office cost",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=withdrawal_account_code,
                    debit=personal_share,
                    memo="Founder personal share paid by TownLIT",
                    line_number=2,
                ),
                JournalLineInput(
                    account_code=bank_account_code,
                    credit=total_paid,
                    memo="Payment made from TownLIT bank",
                    line_number=3,
                ),
            ],
        )
    )