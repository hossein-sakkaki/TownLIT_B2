# apps/accounting/reports/filters.py

from dataclasses import dataclass
from datetime import date


@dataclass
class ReportFilter:
    """
    Common date filters for reports.
    """

    date_from: date | None = None
    date_to: date | None = None
    include_draft: bool = False