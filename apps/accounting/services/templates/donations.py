# apps/accounting/services/templates/donations.py

from datetime import date
from decimal import Decimal

from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput
from apps.accounting.services.account_lookup import AccountCodes


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
):
    """
    Record a donation received into bank.
    donor_type: individual | church | major
    """

    revenue_code_map = {
        "individual": AccountCodes.INDIVIDUAL_DONATIONS,
        "church": AccountCodes.CHURCH_DONATIONS,
        "major": AccountCodes.MAJOR_GIFTS,
    }

    revenue_account_code = revenue_code_map.get(donor_type, AccountCodes.DONATIONS)

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
                    memo="Donation received in bank",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Donation income recognized",
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
):
    """
    Record a donation pledge before cash is received.
    """

    revenue_code_map = {
        "individual": AccountCodes.INDIVIDUAL_DONATIONS,
        "church": AccountCodes.CHURCH_DONATIONS,
        "major": AccountCodes.MAJOR_GIFTS,
    }

    revenue_account_code = revenue_code_map.get(donor_type, AccountCodes.DONATIONS)

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
                    memo="Donation pledge receivable",
                ),
                JournalLineInput(
                    account_code=revenue_account_code,
                    credit=Decimal(amount),
                    memo="Donation pledge recognized",
                ),
            ],
        )
    )