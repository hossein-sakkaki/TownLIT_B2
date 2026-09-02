# apps/accounting/services/cash_activity_service.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
from uuid import uuid4

from django.db import transaction

from apps.accounting.models.account import Account
from apps.accounting.models.bank import BankAccount
from apps.accounting.services.posting_engine import post_journal_entry
from apps.accounting.services.schemas import JournalEntryInput, JournalLineInput


ZERO = Decimal("0.00")


class CashActivityError(Exception):
    pass


def _validate_bank(bank_account: BankAccount) -> None:
    if not bank_account.is_active or bank_account.status != BankAccount.STATUS_ACTIVE:
        raise CashActivityError("Selected bank account is not active.")
    if not bank_account.ledger_account.is_active or not bank_account.ledger_account.allows_posting:
        raise CashActivityError("Selected bank account does not have an active postable ledger account.")


def _line_tracking_kwargs(*, fund=None, budget_line=None) -> dict:
    payload = {}
    if fund:
        payload["fund_code"] = fund.code
    if budget_line:
        payload["budget_line_id"] = budget_line.id
        payload["budget_line_code"] = budget_line.code
        payload["budget_plan_code"] = budget_line.budget.code
    return payload


@transaction.atomic
def record_cash_expense(
    *,
    entry_date,
    bank_account,
    expense_account,
    amount,
    description,
    reference="",
    fund=None,
    budget_line=None,
    created_by=None,
):
    _validate_bank(bank_account)

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= ZERO:
        raise CashActivityError("Expense amount must be greater than zero.")

    if expense_account.account_type != Account.TYPE_EXPENSE:
        raise CashActivityError("Expense must use an EXPENSE ledger account.")

    tracking = _line_tracking_kwargs(fund=fund, budget_line=budget_line)
    source_ref = uuid4().hex

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description.strip(),
            reference=(reference or "").strip(),
            source_app="accounting_admin",
            source_model="cash_expense",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=created_by,
            lines=[
                JournalLineInput(
                    line_number=1,
                    account_code=expense_account.code,
                    debit=amount,
                    memo=description.strip(),
                    **tracking,
                ),
                JournalLineInput(
                    line_number=2,
                    account_code=bank_account.ledger_account.code,
                    credit=amount,
                    memo=(reference or description).strip(),
                ),
            ],
        )
    )


@transaction.atomic
def record_cash_income(
    *,
    entry_date,
    bank_account,
    revenue_account,
    amount,
    description,
    reference="",
    fund=None,
    created_by=None,
):
    _validate_bank(bank_account)

    amount = Decimal(amount).quantize(Decimal("0.01"))
    if amount <= ZERO:
        raise CashActivityError("Income amount must be greater than zero.")

    if revenue_account.account_type != Account.TYPE_REVENUE:
        raise CashActivityError("Income must use a REVENUE ledger account.")

    tracking = _line_tracking_kwargs(fund=fund, budget_line=None)
    source_ref = uuid4().hex

    return post_journal_entry(
        JournalEntryInput(
            entry_date=entry_date,
            description=description.strip(),
            reference=(reference or "").strip(),
            source_app="accounting_admin",
            source_model="cash_income",
            source_ref=source_ref,
            created_by=created_by,
            approved_by=created_by,
            lines=[
                JournalLineInput(
                    line_number=1,
                    account_code=bank_account.ledger_account.code,
                    debit=amount,
                    memo=(reference or description).strip(),
                ),
                JournalLineInput(
                    line_number=2,
                    account_code=revenue_account.code,
                    credit=amount,
                    memo=description.strip(),
                    **tracking,
                ),
            ],
        )
    )
