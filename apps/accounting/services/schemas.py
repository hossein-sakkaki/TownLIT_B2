# apps/accounting/services/schemas.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class JournalLineInput:
    account_code: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    memo: str = ""
    line_number: int | None = None

    # Fund dimension
    fund_code: str | None = None

    # Legacy budget-line alias
    budget_code: str | None = None

    # Canonical budget dimensions
    budget_line_code: str | None = None
    budget_plan_code: str | None = None
    budget_line_id: int | None = None


@dataclass
class JournalEntryInput:
    entry_date: date
    description: str
    lines: list[JournalLineInput] = field(default_factory=list)
    reference: str = ""
    source_app: str = ""
    source_model: str = ""
    source_ref: str = ""
    internal_note: str = ""
    currency: str = "CAD"
    created_by: Any | None = None
    approved_by: Any | None = None