# apps/accounting/seeds/payroll_config.py

from decimal import Decimal
from datetime import date

from apps.accounting.models import (
    PayrollYearConfig,
    PaySchedule,
    PayPeriod,
    PayrollLeavePolicy,
)


def seed_payroll_config_2026():
    """
    Seed initial 2026 payroll rules for BC.
    Admin can update these values annually.
    """

    PayrollYearConfig.objects.update_or_create(
        year=2026,
        province="BC",
        defaults={
            "country": "CA",
            "currency": "CAD",
            "cpp_enabled": True,
            "cpp_rate_employee": Decimal("0.05950"),
            "cpp_rate_employer": Decimal("0.05950"),
            "cpp_basic_exemption_annual": Decimal("3500.00"),
            "cpp_max_pensionable_earnings": Decimal("74600.00"),
            "cpp2_enabled": True,
            "cpp2_rate_employee": Decimal("0.04000"),
            "cpp2_rate_employer": Decimal("0.04000"),
            "cpp2_max_additional_earnings": Decimal("85000.00"),
            "ei_enabled": True,
            "ei_rate_employee": Decimal("0.01630"),
            "ei_rate_employer_multiplier": Decimal("1.40000"),
            "ei_max_insurable_earnings": Decimal("68900.00"),
            "default_federal_td1_amount": Decimal("0.00"),
            "default_provincial_td1_amount": Decimal("0.00"),
            "federal_tax_config": {
                "periods_per_year": 12,
                "credit_rate": "0.14",
                "employment_amount": "1501.20",
                "cpp_base_rate_employee": "0.04950",
                "cpp_first_additional_rate_employee": "0.01000",
                "deduct_cpp_first_additional_from_income": True,
                "brackets": [
                    {"up_to": "58523.00", "rate": "0.1400", "constant": "0.00"},
                    {"up_to": "117045.00", "rate": "0.2050", "constant": "3804.00"},
                    {"up_to": "181440.00", "rate": "0.2600", "constant": "10241.00"},
                    {"up_to": "258482.00", "rate": "0.2900", "constant": "15685.00"},
                    {"up_to": None, "rate": "0.3300", "constant": "26024.00"},
                ],
                "credits": {
                    "basic_personal_amount": "16452.00",
                    "canada_employment_amount": "1501.20",
                    "include_cpp_base_credit": True,
                    "include_ei_credit": True,
                },
                "note": "T4127-oriented configurable federal tax setup. Verify against CRA PDOC before disabling overrides.",
            },
            "provincial_tax_config": {
                "periods_per_year": 12,
                "credit_rate": "0.0506",
                "cpp_base_rate_employee": "0.04950",
                "cpp_first_additional_rate_employee": "0.01000",
                "deduct_cpp_first_additional_from_income": True,
                "brackets": [
                    {"up_to": "50363.00", "rate": "0.0506", "constant": "0.00"},
                    {"up_to": "100728.00", "rate": "0.0770", "constant": "1330.00"},
                    {"up_to": "115648.00", "rate": "0.1050", "constant": "4150.00"},
                    {"up_to": "140430.00", "rate": "0.1229", "constant": "6220.00"},
                    {"up_to": "190405.00", "rate": "0.1470", "constant": "9604.00"},
                    {"up_to": "265545.00", "rate": "0.1680", "constant": "13603.00"},
                    {"up_to": None, "rate": "0.2050", "constant": "23428.00"},
                ],
                "credits": {
                    "basic_personal_amount": "13216.00",
                    "include_cpp_base_credit": True,
                    "include_ei_credit": True,
                },
                "low_income_reduction": {
                    "enabled": True,
                    "max_amount": "575.00",
                    "threshold": "25570.90",
                    "reduction_rate": "0.0356",
                },
                "note": "BC 2026 January-June configurable setup based on CRA T4127 Table 8.1. Verify against CRA PDOC before disabling overrides.",
            },
            "note": "Initial 2026 BC payroll config. CPP/EI seeded from public CRA/ESDC values; tax tables intentionally left configurable.",
            "is_active": True,
        },
    )


def seed_monthly_pay_schedule():
    """
    Seed monthly payroll schedule.
    """

    PaySchedule.objects.update_or_create(
        code="MONTHLY",
        defaults={
            "name": "Monthly Payroll",
            "frequency": PaySchedule.FREQ_MONTHLY,
            "description": "Monthly payroll schedule for TownLIT.",
            "is_active": True,
        },
    )


def seed_pay_period_may_2026():
    """
    Seed first May 2026 pay period.
    """

    schedule, _ = PaySchedule.objects.get_or_create(
        code="MONTHLY",
        defaults={
            "name": "Monthly Payroll",
            "frequency": PaySchedule.FREQ_MONTHLY,
            "description": "Monthly payroll schedule for TownLIT.",
            "is_active": True,
        },
    )

    PayPeriod.objects.update_or_create(
        code="PAY-2026-05",
        defaults={
            "schedule": schedule,
            "tax_year": 2026,
            "start_date": date(2026, 5, 1),
            "end_date": date(2026, 5, 31),
            "pay_date": date(2026, 6, 1),
            "status": PayPeriod.STATUS_OPEN,
            "note": "First TownLIT payroll period for May 2026, paid on June 1, 2026.",
        },
    )


def seed_default_leave_policies():
    """
    Seed baseline leave policies for BC.
    """

    PayrollLeavePolicy.objects.update_or_create(
        code="BC-VACATION-4PCT",
        defaults={
            "name": "BC Vacation Pay - 4%",
            "leave_type": PayrollLeavePolicy.TYPE_VACATION,
            "province": "BC",
            "is_paid": True,
            "accrual_config": {
                "method": "percentage_of_wages",
                "rate": "0.04",
            },
            "eligibility_config": {
                "note": "Baseline configurable vacation policy. Review against current BC employment standards.",
            },
            "is_active": True,
            "note": "Default vacation pay policy for initial payroll setup.",
        },
    )

    PayrollLeavePolicy.objects.update_or_create(
        code="BC-SICK-TRACKING",
        defaults={
            "name": "BC Sick Leave Tracking",
            "leave_type": PayrollLeavePolicy.TYPE_SICK,
            "province": "BC",
            "is_paid": True,
            "accrual_config": {
                "method": "manual_or_policy_based",
            },
            "eligibility_config": {
                "note": "Configurable sick leave policy. Review BC employment standards before production use.",
            },
            "is_active": True,
            "note": "Default sick leave tracking policy for future use.",
        },
    )


def seed_payroll_foundation_2026():
    """
    Seed all initial payroll foundation records.
    """

    seed_payroll_config_2026()
    seed_monthly_pay_schedule()
    seed_pay_period_may_2026()
    seed_default_leave_policies()