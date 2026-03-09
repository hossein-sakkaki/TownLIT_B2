# apps/accounting/services/schemas.py

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional, List, Any


@dataclass
class JournalLineInput:
    """
    Input schema for one journal line.
    """

    account_code: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    memo: str = ""
    line_number: int = 1

    # Fund / budget tagging
    fund_code: Optional[str] = None
    budget_code: Optional[str] = None


@dataclass
class JournalEntryInput:
    """
    Input schema for posting a journal entry.
    """

    entry_date: date
    description: str
    lines: List[JournalLineInput] = field(default_factory=list)

    reference: str = ""
    source_app: str = ""
    source_model: str = ""
    source_ref: str = ""
    internal_note: str = ""
    currency: str = "CAD"

    created_by: Optional[Any] = None
    approved_by: Optional[Any] = None