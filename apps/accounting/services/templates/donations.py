# apps/accounting/services/templates/donations.py
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


def record_donation_received(
    *,
    entry_date: date,
    amount: Decimal,
    donor_type: str,
    description: str,
    reference: str = "",
    source_app: str = "advancement",
    source_model: str = "donation",
    source_ref: str = "",
    bank_account_code: str = AccountCodes.BANK,
    created_by=None,
    approved_by=None,
):
    """Record received donation revenue."""

    revenue_code_map = {
        "individual": AccountCodes.INDIVIDUAL_DONATIONS,
        "church": AccountCodes.CHURCH_DONATIONS,
        "major": AccountCodes.MAJOR_GIFTS,
    }

    revenue_account_code = revenue_code_map.get(
        donor_type,
        AccountCodes.DONATIONS,
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
                    memo="Donation received in bank",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Donation income recognized",
                    line_number=2,
                ),
            ],
        )
    )


def record_donation_pledge(
    *,
    entry_date: date,
    amount: Decimal,
    donor_type: str,
    description: str,
    reference: str = "",
    source_app: str = "advancement",
    source_model: str = "donation_pledge",
    source_ref: str = "",
    receivable_account_code: str = AccountCodes.PLEDGED_DONATIONS,
    created_by=None,
    approved_by=None,
):
    """Record donation pledge receivable."""

    revenue_code_map = {
        "individual": AccountCodes.INDIVIDUAL_DONATIONS,
        "church": AccountCodes.CHURCH_DONATIONS,
        "major": AccountCodes.MAJOR_GIFTS,
    }

    revenue_account_code = revenue_code_map.get(
        donor_type,
        AccountCodes.DONATIONS,
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
                    memo="Donation pledge receivable",
                    line_number=1,
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=amount,
                    memo="Donation pledge recognized",
                    line_number=2,
                ),
            ],
        )
    )