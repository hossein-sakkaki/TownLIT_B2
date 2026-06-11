# apps/accounting/services/payroll/schemas.py

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass
class PayrollCalculationInput:
    """
    Input for one employee payroll calculation.
    Manual override fields allow official CRA/PDOC values.
    """

    employee_id: int
    compensation_plan_id: int | None

    gross_salary: Decimal
    actual_paid: Decimal

    pay_period_start: date
    pay_period_end: date
    pay_date: date
    tax_year: int
    
    # When False, payroll skips regular salary/hourly pay.
    include_regular_pay: bool = True

    # One-time taxable components
    vacation_pay_paid: Decimal = Decimal("0.00")
    sick_pay_paid: Decimal = Decimal("0.00")
    taxable_benefits: Decimal = Decimal("0.00")
    
    
    other_employee_deductions: Decimal = Decimal("0.00")
    other_employer_contributions: Decimal = Decimal("0.00")

    # Optional official/manual overrides.
    override_employee_cpp: Decimal | None = None
    override_employer_cpp: Decimal | None = None
    override_employee_cpp2: Decimal | None = None
    override_employer_cpp2: Decimal | None = None
    override_employee_ei: Decimal | None = None
    override_employer_ei: Decimal | None = None
    override_federal_income_tax: Decimal | None = None
    override_provincial_income_tax: Decimal | None = None

    override_source: str = ""
    override_note: str = ""

    payment_reference: str = ""
    payment_note: str = ""

    regular_hours: Decimal = Decimal("0.00")
    daily_overtime_hours: Decimal = Decimal("0.00")
    weekly_overtime_hours: Decimal = Decimal("0.00")
    double_time_hours: Decimal = Decimal("0.00")
    work_summary_id: int | None = None

@dataclass
class PayrollCalculationResult:
    """
    Calculated payroll values for one employee.
    """

    employee_id: int
    compensation_plan_id: int | None

    gross_salary: Decimal

    vacation_pay_earned: Decimal
    vacation_pay_paid: Decimal
    sick_pay_paid: Decimal
    taxable_benefits: Decimal

    pensionable_earnings: Decimal
    insurable_earnings: Decimal
    taxable_earnings: Decimal

    employee_cpp: Decimal
    employee_cpp2: Decimal
    employee_ei: Decimal

    federal_income_tax: Decimal
    provincial_income_tax: Decimal
    other_employee_deductions: Decimal

    total_employee_deductions: Decimal

    employer_cpp: Decimal
    employer_cpp2: Decimal
    employer_ei: Decimal
    other_employer_contributions: Decimal

    total_employer_contributions: Decimal

    net_pay: Decimal
    actual_paid: Decimal
    net_salary_payable: Decimal

    total_remittance_due: Decimal

    payment_reference: str
    payment_note: str

    calculation_snapshot: dict[str, Any]
    
    pay_type: str
    hourly_rate: Decimal
    regular_hours: Decimal
    daily_overtime_hours: Decimal
    weekly_overtime_hours: Decimal
    double_time_hours: Decimal
    regular_pay: Decimal
    daily_overtime_pay: Decimal
    weekly_overtime_pay: Decimal
    double_time_pay: Decimal
    work_summary_id: int | None