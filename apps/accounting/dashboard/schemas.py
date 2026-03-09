# apps/accounting/dashboard/schemas.py

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List


@dataclass
class DashboardKPI:
    """
    Generic KPI card.
    """

    key: str
    label: str
    value: str
    currency: str = "CAD"
    status: str = "neutral"


@dataclass
class MonthlyTrendPoint:
    """
    Monthly revenue/expense trend point.
    """

    period: str
    revenue_total: Decimal
    expense_total: Decimal
    net_result: Decimal


@dataclass
class FundBalanceRow:
    """
    Fund balance summary row.
    """

    fund_code: str
    fund_name: str
    fund_type: str
    revenue_total: Decimal
    expense_total: Decimal
    remaining_balance: Decimal
    total_awarded: Decimal


@dataclass
class ReconciliationAlertRow:
    """
    Reconciliation alert row.
    """

    bank_account_code: str
    bank_account_name: str
    period_start: str
    period_end: str
    unreconciled_difference: Decimal
    status: str


@dataclass
class DashboardPayload:
    """
    Full accounting dashboard payload.
    """

    currency: str = "CAD"
    kpis: List[DashboardKPI] = field(default_factory=list)
    monthly_trend: List[MonthlyTrendPoint] = field(default_factory=list)
    fund_balances: List[FundBalanceRow] = field(default_factory=list)
    reconciliation_alerts: List[ReconciliationAlertRow] = field(default_factory=list)