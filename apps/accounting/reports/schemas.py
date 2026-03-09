# apps/accounting/reports/schemas.py

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List


@dataclass
class TrialBalanceRow:
    """
    One row in the trial balance report.
    """

    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal


@dataclass
class TrialBalanceReport:
    """
    Full trial balance report payload.
    """

    title: str
    date_from: date | None
    date_to: date | None
    rows: List[TrialBalanceRow] = field(default_factory=list)
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")


@dataclass
class GeneralLedgerRow:
    """
    One ledger line for a specific account.
    """

    entry_number: str
    entry_date: date
    reference: str
    description: str
    source_app: str
    source_model: str
    source_ref: str
    line_memo: str
    debit: Decimal
    credit: Decimal
    running_balance: Decimal


@dataclass
class GeneralLedgerReport:
    """
    Full general ledger payload for one account.
    """

    title: str
    account_code: str
    account_name: str
    account_type: str
    normal_balance: str
    date_from: date | None
    date_to: date | None
    rows: List[GeneralLedgerRow] = field(default_factory=list)
    total_debit: Decimal = Decimal("0.00")
    total_credit: Decimal = Decimal("0.00")
    ending_balance: Decimal = Decimal("0.00")


@dataclass
class FounderBalanceSummary:
    """
    Founder accounting summary.
    """

    title: str
    founder_loan_account_code: str
    founder_loan_account_name: str
    founder_withdrawal_account_code: str
    founder_withdrawal_account_name: str
    date_from: date | None
    date_to: date | None
    total_loans: Decimal
    total_withdrawals: Decimal
    net_founder_balance: Decimal


@dataclass
class MonthlySummaryRow:
    """
    One monthly financial summary row.
    """

    period: str
    revenue_total: Decimal
    expense_total: Decimal
    net_result: Decimal


@dataclass
class MonthlySummaryReport:
    """
    Monthly summary report payload.
    """

    title: str
    date_from: date | None
    date_to: date | None
    rows: List[MonthlySummaryRow] = field(default_factory=list)
    total_revenue: Decimal = Decimal("0.00")
    total_expense: Decimal = Decimal("0.00")
    total_net_result: Decimal = Decimal("0.00")