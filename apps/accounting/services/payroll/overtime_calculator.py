# apps/accounting/services/payroll/overtime_calculator.py

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@dataclass
class DailyWorkInput:
    """
    Raw daily hours input from a future attendance/time-clock system.
    """

    work_date: date
    hours_worked: Decimal


@dataclass
class OvertimeBreakdown:
    """
    Final summarized hours for payroll.
    """

    regular_hours: Decimal = ZERO
    daily_overtime_hours: Decimal = ZERO
    weekly_overtime_hours: Decimal = ZERO
    double_time_hours: Decimal = ZERO


class BCCanadaOvertimeCalculator:
    """
    Calculates BC-style daily and weekly overtime from daily work inputs.

    Weekly overtime uses only the first 8 hours worked each day.
    """

    def calculate(
        self,
        *,
        daily_entries: list[DailyWorkInput],
        daily_overtime_after_hours: Decimal = Decimal("8.00"),
        daily_double_time_after_hours: Decimal = Decimal("12.00"),
        weekly_overtime_after_hours: Decimal = Decimal("40.00"),
    ) -> OvertimeBreakdown:
        """
        Return summarized payroll hours.
        """

        breakdown = OvertimeBreakdown()

        weekly_regular_candidates = defaultdict(lambda: ZERO)

        for item in daily_entries:
            hours = self._hours(item.hours_worked)

            if hours <= ZERO:
                continue

            regular_candidate = min(hours, daily_overtime_after_hours)

            daily_ot = ZERO
            double_time = ZERO

            if hours > daily_overtime_after_hours:
                daily_ot = min(
                    hours,
                    daily_double_time_after_hours,
                ) - daily_overtime_after_hours

            if hours > daily_double_time_after_hours:
                double_time = hours - daily_double_time_after_hours

            week_start = self._sunday_week_start(item.work_date)

            weekly_regular_candidates[week_start] += regular_candidate

            breakdown.regular_hours += regular_candidate
            breakdown.daily_overtime_hours += daily_ot
            breakdown.double_time_hours += double_time

        # Convert regular candidate hours above weekly threshold into weekly OT.
        for week_start, candidate_hours in weekly_regular_candidates.items():
            if candidate_hours <= weekly_overtime_after_hours:
                continue

            weekly_ot = candidate_hours - weekly_overtime_after_hours
            breakdown.weekly_overtime_hours += weekly_ot
            breakdown.regular_hours -= weekly_ot

        breakdown.regular_hours = self._hours(breakdown.regular_hours)
        breakdown.daily_overtime_hours = self._hours(breakdown.daily_overtime_hours)
        breakdown.weekly_overtime_hours = self._hours(breakdown.weekly_overtime_hours)
        breakdown.double_time_hours = self._hours(breakdown.double_time_hours)

        return breakdown

    def _sunday_week_start(self, value: date) -> date:
        """
        Return Sunday as week start.
        """

        # Python weekday: Monday=0 ... Sunday=6
        days_since_sunday = (value.weekday() + 1) % 7
        return value - timedelta(days=days_since_sunday)

    def _hours(self, value) -> Decimal:
        """
        Normalize hours to 2 decimals.
        """

        return Decimal(str(value or ZERO)).quantize(CENT, rounding=ROUND_HALF_UP)