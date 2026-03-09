# apps/accounting/services/templates/revenue.py

from datetime import date
from decimal import Decimal

from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from apps.accounting.services.account_lookup import AccountCodes


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
):
    """
    Record subscription revenue received in cash.
    """

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
                    memo="Subscription payment received",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Subscription revenue recognized",
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
):
    """
    Record advertisement revenue received in cash.
    """

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
                    memo="Ad payment received",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Ad revenue recognized",
                ),
            ],
        )
    )