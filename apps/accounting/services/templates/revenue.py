# apps/accounting/services/templates/revenue.py
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


def record_subscription_revenue(
    *,
    entry_date: date,
    amount: Decimal,
    description: str,
    reference: str = "",
    source_app: str = "payment",
    source_model: str = "subscription_payment",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    revenue_account_code: str = AccountCodes.MONTHLY_SUBSCRIPTION,
    created_by=None,
    approved_by=None,
):
    """Record subscription revenue."""

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
                    memo="Subscription payment received",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Subscription revenue recognized",
                    line_number=2,
                ),
            ],
        )
    )


def record_advertisement_revenue(
    *,
    entry_date: date,
    amount: Decimal,
    description: str,
    reference: str = "",
    source_app: str = "payment",
    source_model: str = "advertisement_payment",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    revenue_account_code: str = AccountCodes.ADVERTISEMENT_REVENUE,
    created_by=None,
    approved_by=None,
):
    """Record advertisement revenue."""

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
                    memo="Ad payment received",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Ad revenue recognized",
                    line_number=2,
                ),
            ],
        )
    )