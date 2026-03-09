# apps/accounting/services/period_generation_service.py

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from apps.accounting.models import AccountingPeriod


@dataclass
class PeriodGenerationResult:
    """
    Result payload for period generation.
    """

    fiscal_year_label: str
    created_or_updated_count: int


def generate_fiscal_year_periods(
    *,
    fy_start_year: int,
    default_status: str = AccountingPeriod.STATUS_OPEN,
) -> PeriodGenerationResult:
    """
    Create or update TownLIT fiscal-year monthly periods.

    TownLIT fiscal year runs from June 1 to May 31.
    Example:
        fy_start_year=2025 -> FY2026 -> Jun 2025 ... May 2026
    """

    fiscal_year_label = f"FY{fy_start_year + 1}"
    created_or_updated_count = 0

    months = [
        (fy_start_year, 6),
        (fy_start_year, 7),
        (fy_start_year, 8),
        (fy_start_year, 9),
        (fy_start_year, 10),
        (fy_start_year, 11),
        (fy_start_year, 12),
        (fy_start_year + 1, 1),
        (fy_start_year + 1, 2),
        (fy_start_year + 1, 3),
        (fy_start_year + 1, 4),
        (fy_start_year + 1, 5),
    ]

    for year, month in months:
        start_date = date(year, month, 1)
        end_date = date(year, month, monthrange(year, month)[1])

        code = f"{fiscal_year_label}-{year}-{month:02d}"
        name = f"{fiscal_year_label} {start_date.strftime('%B %Y')}"

        AccountingPeriod.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "fiscal_year_label": fiscal_year_label,
                "period_type": AccountingPeriod.PERIOD_TYPE_MONTH,
                "start_date": start_date,
                "end_date": end_date,
                "status": default_status,
            },
        )
        created_or_updated_count += 1

    return PeriodGenerationResult(
        fiscal_year_label=fiscal_year_label,
        created_or_updated_count=created_or_updated_count,
    )