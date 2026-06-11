# apps/accounting/services/payroll/calculation_engine.py

from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from apps.accounting.models import (
    PayrollYearConfig,
    PayrollEmployee,
    PayrollCompensationPlan,
    PayStub,
)

from .schemas import PayrollCalculationInput, PayrollCalculationResult


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


class PayrollCalculationError(Exception):
    """
    Raised when payroll calculation cannot be completed.
    """
    pass


class PayrollCalculationEngine:
    """
    Calculates payroll from configurable yearly rules.
    """

    def calculate(
        self,
        *,
        item: PayrollCalculationInput,
        config: PayrollYearConfig,
    ) -> PayrollCalculationResult:
        """
        Calculate one pay stub.
        """

        employee = PayrollEmployee.objects.get(id=item.employee_id)

        compensation_plan = None
        if item.compensation_plan_id:
            compensation_plan = PayrollCompensationPlan.objects.get(
                id=item.compensation_plan_id,
                employee=employee,
            )

        pay_components = self._build_gross_pay(
            item=item,
            compensation_plan=compensation_plan,
        )

        gross_salary = pay_components["gross_salary"]
        actual_paid = self._money(item.actual_paid)

        if gross_salary < ZERO:
            raise PayrollCalculationError("gross_salary cannot be negative.")

        if actual_paid < ZERO:
            raise PayrollCalculationError("actual_paid cannot be negative.")

        vacation_pay_earned = self._calculate_vacation_pay_earned(
            gross_salary=gross_salary,
            compensation_plan=compensation_plan,
        )

        requested_vacation_pay_paid = self._money(item.vacation_pay_paid)

        if requested_vacation_pay_paid > ZERO:
            vacation_pay_paid = requested_vacation_pay_paid
        else:
            vacation_pay_paid = self._calculate_vacation_pay_paid(
                vacation_pay_earned=vacation_pay_earned,
                compensation_plan=compensation_plan,
            )

        sick_pay_paid = self._money(item.sick_pay_paid)
        taxable_benefits = self._money(item.taxable_benefits)

        taxable_earnings = self._money(
            gross_salary
            + vacation_pay_paid
            + sick_pay_paid
            + taxable_benefits
        )

        pensionable_earnings = taxable_earnings if not employee.cpp_exempt else ZERO
        insurable_earnings = taxable_earnings if not employee.ei_exempt else ZERO

        ytd_pensionable = self._get_ytd_amount(
            employee=employee,
            tax_year=item.tax_year,
            field="pensionable_earnings",
        )

        ytd_insurable = self._get_ytd_amount(
            employee=employee,
            tax_year=item.tax_year,
            field="insurable_earnings",
        )

        calculated_employee_cpp = self._calculate_cpp(
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            employer_side=False,
        )

        calculated_employer_cpp = self._calculate_cpp(
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            employer_side=True,
        )

        calculated_employee_cpp2 = self._calculate_cpp2(
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            employer_side=False,
        )

        calculated_employer_cpp2 = self._calculate_cpp2(
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            employer_side=True,
        )

        calculated_employee_ei = self._calculate_ei(
            current_insurable=insurable_earnings,
            ytd_insurable=ytd_insurable,
            config=config,
            employee=employee,
            employer_side=False,
        )

        calculated_employer_ei = self._calculate_ei(
            current_insurable=insurable_earnings,
            ytd_insurable=ytd_insurable,
            config=config,
            employee=employee,
            employer_side=True,
        )

        calculated_federal_income_tax = self._calculate_income_tax_v2(
            taxable_earnings=taxable_earnings,
            employee_cpp=calculated_employee_cpp,
            employee_ei=calculated_employee_ei,
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            tax_config=config.federal_tax_config,
            exempt=employee.income_tax_exempt,
        )

        calculated_provincial_income_tax = self._calculate_income_tax_v2(
            taxable_earnings=taxable_earnings,
            employee_cpp=calculated_employee_cpp,
            employee_ei=calculated_employee_ei,
            current_pensionable=pensionable_earnings,
            ytd_pensionable=ytd_pensionable,
            config=config,
            tax_config=config.provincial_tax_config,
            exempt=employee.income_tax_exempt,
        )

        # Keep internal auto calculation before manual/official override.
        auto_values = {
            "auto_employee_cpp": str(calculated_employee_cpp),
            "auto_employer_cpp": str(calculated_employer_cpp),
            "auto_employee_cpp2": str(calculated_employee_cpp2),
            "auto_employer_cpp2": str(calculated_employer_cpp2),
            "auto_employee_ei": str(calculated_employee_ei),
            "auto_employer_ei": str(calculated_employer_ei),
            "auto_federal_income_tax": str(calculated_federal_income_tax),
            "auto_provincial_income_tax": str(calculated_provincial_income_tax),
        }
        
        # Official/manual override values, usually entered from CRA PDOC.
        employee_cpp = self._override_money(
            item.override_employee_cpp,
            calculated_employee_cpp,
        )
        employer_cpp = self._override_money(
            item.override_employer_cpp,
            calculated_employer_cpp,
        )
        employee_cpp2 = self._override_money(
            item.override_employee_cpp2,
            calculated_employee_cpp2,
        )
        employer_cpp2 = self._override_money(
            item.override_employer_cpp2,
            calculated_employer_cpp2,
        )
        employee_ei = self._override_money(
            item.override_employee_ei,
            calculated_employee_ei,
        )
        employer_ei = self._override_money(
            item.override_employer_ei,
            calculated_employer_ei,
        )
        federal_income_tax = self._override_money(
            item.override_federal_income_tax,
            calculated_federal_income_tax,
        )
        provincial_income_tax = self._override_money(
            item.override_provincial_income_tax,
            calculated_provincial_income_tax,
        )

        other_employee_deductions = self._money(item.other_employee_deductions)
        other_employer_contributions = self._money(item.other_employer_contributions)

        total_employee_deductions = self._money(
            employee_cpp
            + employee_cpp2
            + employee_ei
            + federal_income_tax
            + provincial_income_tax
            + other_employee_deductions
        )

        total_employer_contributions = self._money(
            employer_cpp
            + employer_cpp2
            + employer_ei
            + other_employer_contributions
        )

        net_pay = self._money(taxable_earnings - total_employee_deductions)

        if net_pay < ZERO:
            raise PayrollCalculationError(
                "Calculated net_pay cannot be negative. Review deductions and overrides."
            )

        if actual_paid > net_pay:
            raise PayrollCalculationError("actual_paid cannot exceed calculated net_pay.")

        net_salary_payable = self._money(net_pay - actual_paid)

        total_remittance_due = self._money(
            employee_cpp
            + employer_cpp
            + employee_cpp2
            + employer_cpp2
            + employee_ei
            + employer_ei
            + federal_income_tax
            + provincial_income_tax
        )

        snapshot = {
            "tax_year": config.year,
            "province": config.province,
            "employee_id": employee.id,
            "employee_display_name": employee.display_name,
            "compensation_plan_id": compensation_plan.id if compensation_plan else None,
            "gross_salary": str(gross_salary),
            "actual_paid": str(actual_paid),
            "vacation_pay_earned": str(vacation_pay_earned),
            "vacation_pay_paid": str(vacation_pay_paid),
                        "include_regular_pay": getattr(item, "include_regular_pay", True),
            "is_standalone_vacation_pay": (
                not getattr(item, "include_regular_pay", True)
                and vacation_pay_paid > ZERO
            ),
            
            "sick_pay_paid": str(sick_pay_paid),
            "taxable_benefits": str(taxable_benefits),
            "taxable_earnings": str(taxable_earnings),
            "pensionable_earnings": str(pensionable_earnings),
            "insurable_earnings": str(insurable_earnings),
            "ytd_pensionable_before_run": str(ytd_pensionable),
            "ytd_insurable_before_run": str(ytd_insurable),
            "calculated_values": {
                "employee_cpp": str(calculated_employee_cpp),
                "employer_cpp": str(calculated_employer_cpp),
                "employee_cpp2": str(calculated_employee_cpp2),
                "employer_cpp2": str(calculated_employer_cpp2),
                "employee_ei": str(calculated_employee_ei),
                "employer_ei": str(calculated_employer_ei),
                "federal_income_tax": str(calculated_federal_income_tax),
                "provincial_income_tax": str(calculated_provincial_income_tax),
            },
            "final_values": {
                "employee_cpp": str(employee_cpp),
                "employer_cpp": str(employer_cpp),
                "employee_cpp2": str(employee_cpp2),
                "employer_cpp2": str(employer_cpp2),
                "employee_ei": str(employee_ei),
                "employer_ei": str(employer_ei),
                "federal_income_tax": str(federal_income_tax),
                "provincial_income_tax": str(provincial_income_tax),
                "total_employee_deductions": str(total_employee_deductions),
                "total_employer_contributions": str(total_employer_contributions),
                "net_pay": str(net_pay),
                "net_salary_payable": str(net_salary_payable),
                "total_remittance_due": str(total_remittance_due),
            },
            "manual_overrides": {
                "has_manual_overrides": self._has_overrides(item),
                "override_source": item.override_source,
                "override_note": item.override_note,
                "employee_cpp": self._decimal_or_none(item.override_employee_cpp),
                "employer_cpp": self._decimal_or_none(item.override_employer_cpp),
                "employee_cpp2": self._decimal_or_none(item.override_employee_cpp2),
                "employer_cpp2": self._decimal_or_none(item.override_employer_cpp2),
                "employee_ei": self._decimal_or_none(item.override_employee_ei),
                "employer_ei": self._decimal_or_none(item.override_employer_ei),
                "federal_income_tax": self._decimal_or_none(item.override_federal_income_tax),
                "provincial_income_tax": self._decimal_or_none(item.override_provincial_income_tax),
            },
            "config_snapshot": {
                "cpp_enabled": config.cpp_enabled,
                "cpp_rate_employee": str(config.cpp_rate_employee),
                "cpp_rate_employer": str(config.cpp_rate_employer),
                "cpp_basic_exemption_annual": str(config.cpp_basic_exemption_annual),
                "cpp_max_pensionable_earnings": str(config.cpp_max_pensionable_earnings),
                "cpp2_enabled": config.cpp2_enabled,
                "cpp2_rate_employee": str(config.cpp2_rate_employee),
                "cpp2_rate_employer": str(config.cpp2_rate_employer),
                "cpp2_max_additional_earnings": str(config.cpp2_max_additional_earnings),
                "ei_enabled": config.ei_enabled,
                "ei_rate_employee": str(config.ei_rate_employee),
                "ei_rate_employer_multiplier": str(config.ei_rate_employer_multiplier),
                "ei_max_insurable_earnings": str(config.ei_max_insurable_earnings),
            },
            "note": (
                "Calculated values come from PayrollYearConfig. "
                "Manual overrides should normally come from CRA PDOC or reviewed official payroll tables."
            ),
            "pay_type": pay_components["pay_type"],
            "hourly_rate": str(pay_components["hourly_rate"]),
            "regular_hours": str(pay_components["regular_hours"]),
            "daily_overtime_hours": str(pay_components["daily_overtime_hours"]),
            "weekly_overtime_hours": str(pay_components["weekly_overtime_hours"]),
            "double_time_hours": str(pay_components["double_time_hours"]),
            "regular_pay": str(pay_components["regular_pay"]),
            "daily_overtime_pay": str(pay_components["daily_overtime_pay"]),
            "weekly_overtime_pay": str(pay_components["weekly_overtime_pay"]),
            "double_time_pay": str(pay_components["double_time_pay"]),
            "work_summary_id": item.work_summary_id,
            
            **auto_values,
            "final_employee_cpp": str(employee_cpp),
            "final_employer_cpp": str(employer_cpp),
            "final_employee_cpp2": str(employee_cpp2),
            "final_employer_cpp2": str(employer_cpp2),
            "final_employee_ei": str(employee_ei),
            "final_employer_ei": str(employer_ei),
            "final_federal_income_tax": str(federal_income_tax),
            "final_provincial_income_tax": str(provincial_income_tax),
        }

        return PayrollCalculationResult(
            employee_id=employee.id,
            compensation_plan_id=compensation_plan.id if compensation_plan else None,
            gross_salary=gross_salary,
            vacation_pay_earned=vacation_pay_earned,
            vacation_pay_paid=vacation_pay_paid,
            sick_pay_paid=sick_pay_paid,
            taxable_benefits=taxable_benefits,
            pensionable_earnings=pensionable_earnings,
            insurable_earnings=insurable_earnings,
            taxable_earnings=taxable_earnings,
            employee_cpp=employee_cpp,
            employee_cpp2=employee_cpp2,
            employee_ei=employee_ei,
            federal_income_tax=federal_income_tax,
            provincial_income_tax=provincial_income_tax,
            other_employee_deductions=other_employee_deductions,
            total_employee_deductions=total_employee_deductions,
            employer_cpp=employer_cpp,
            employer_cpp2=employer_cpp2,
            employer_ei=employer_ei,
            other_employer_contributions=other_employer_contributions,
            total_employer_contributions=total_employer_contributions,
            net_pay=net_pay,
            actual_paid=actual_paid,
            net_salary_payable=net_salary_payable,
            total_remittance_due=total_remittance_due,
            payment_reference=item.payment_reference,
            payment_note=item.payment_note,
            calculation_snapshot=snapshot,
            
            pay_type=pay_components["pay_type"],
            hourly_rate=pay_components["hourly_rate"],
            regular_hours=pay_components["regular_hours"],
            daily_overtime_hours=pay_components["daily_overtime_hours"],
            weekly_overtime_hours=pay_components["weekly_overtime_hours"],
            double_time_hours=pay_components["double_time_hours"],
            regular_pay=pay_components["regular_pay"],
            daily_overtime_pay=pay_components["daily_overtime_pay"],
            weekly_overtime_pay=pay_components["weekly_overtime_pay"],
            double_time_pay=pay_components["double_time_pay"],
            work_summary_id=item.work_summary_id,
        )

    def _calculate_vacation_pay_earned(
        self,
        *,
        gross_salary: Decimal,
        compensation_plan: PayrollCompensationPlan | None,
    ) -> Decimal:
        """
        Calculate earned vacation pay.
        """

        if not compensation_plan or not compensation_plan.vacation_pay_enabled:
            return ZERO

        return self._money(gross_salary * compensation_plan.vacation_pay_rate)

    def _calculate_vacation_pay_paid(
        self,
        *,
        vacation_pay_earned: Decimal,
        compensation_plan: PayrollCompensationPlan | None,
    ) -> Decimal:
        """
        Decide whether vacation is paid now or accrued.
        """

        if not compensation_plan:
            return ZERO

        if compensation_plan.vacation_pay_mode == "pay_each_period":
            return vacation_pay_earned

        return ZERO

    def _calculate_cpp(
        self,
        *,
        current_pensionable: Decimal,
        ytd_pensionable: Decimal,
        config: PayrollYearConfig,
        employer_side: bool,
    ) -> Decimal:
        """
        Calculate CPP for the current period.
        """

        if not config.cpp_enabled:
            return ZERO

        annual_max = config.cpp_max_pensionable_earnings or ZERO
        if annual_max <= ZERO:
            return ZERO

        remaining_pensionable_room = max(annual_max - ytd_pensionable, ZERO)
        eligible_pensionable = min(current_pensionable, remaining_pensionable_room)

        # Basic exemption is annual. We prorate monthly by default.
        prorated_exemption = self._money(
            (config.cpp_basic_exemption_annual or ZERO) / Decimal("12")
        )
        contributory_earnings = max(eligible_pensionable - prorated_exemption, ZERO)

        rate = config.cpp_rate_employer if employer_side else config.cpp_rate_employee

        return self._money(contributory_earnings * rate)

    def _calculate_cpp2(
        self,
        *,
        current_pensionable: Decimal,
        ytd_pensionable: Decimal,
        config: PayrollYearConfig,
        employer_side: bool,
    ) -> Decimal:
        """
        Calculate CPP2 for earnings above regular CPP maximum.
        """

        if not config.cpp2_enabled:
            return ZERO

        cpp_max = config.cpp_max_pensionable_earnings or ZERO
        cpp2_max = config.cpp2_max_additional_earnings or ZERO

        if cpp2_max <= cpp_max:
            return ZERO

        current_start = ytd_pensionable
        current_end = ytd_pensionable + current_pensionable

        eligible_start = max(current_start, cpp_max)
        eligible_end = min(current_end, cpp2_max)

        eligible_cpp2 = max(eligible_end - eligible_start, ZERO)

        rate = config.cpp2_rate_employer if employer_side else config.cpp2_rate_employee

        return self._money(eligible_cpp2 * rate)

    def _calculate_ei(
        self,
        *,
        current_insurable: Decimal,
        ytd_insurable: Decimal,
        config: PayrollYearConfig,
        employee: PayrollEmployee,
        employer_side: bool,
    ) -> Decimal:
        """
        Calculate EI when enabled and not exempt.
        """

        if not config.ei_enabled or employee.ei_exempt:
            return ZERO

        annual_max = config.ei_max_insurable_earnings or ZERO
        if annual_max <= ZERO:
            return ZERO

        remaining_room = max(annual_max - ytd_insurable, ZERO)
        eligible_insurable = min(current_insurable, remaining_room)

        if employer_side:
            return self._money(
                eligible_insurable
                * config.ei_rate_employee
                * config.ei_rate_employer_multiplier
            )

        return self._money(eligible_insurable * config.ei_rate_employee)

    def _calculate_income_tax(
        self,
        *,
        taxable_earnings: Decimal,
        tax_config: dict,
        td1_amount: Decimal,
        exempt: bool,
    ) -> Decimal:
        """
        Calculate simplified period tax from configurable brackets.

        This is intentionally configurable and should be aligned with
        official CRA formulas before production use.
        """

        if exempt:
            return ZERO

        if not tax_config:
            return ZERO

        periods_per_year = Decimal(str(tax_config.get("periods_per_year", 12)))
        brackets = tax_config.get("brackets", [])

        if not brackets:
            return ZERO

        annualized_income = taxable_earnings * periods_per_year
        annual_tax = ZERO
        previous_limit = ZERO

        for bracket in brackets:
            up_to_raw = bracket.get("up_to")
            rate = Decimal(str(bracket.get("rate", "0")))

            if up_to_raw is None:
                bracket_limit = annualized_income
            else:
                bracket_limit = Decimal(str(up_to_raw))

            taxable_in_bracket = max(
                min(annualized_income, bracket_limit) - previous_limit,
                ZERO,
            )

            annual_tax += taxable_in_bracket * rate
            previous_limit = bracket_limit

            if annualized_income <= bracket_limit:
                break

        # Basic credit approximation.
        basic_credit_rate = Decimal(str(tax_config.get("basic_credit_rate", "0")))
        annual_tax -= (td1_amount or ZERO) * basic_credit_rate

        annual_tax = max(annual_tax, ZERO)

        return self._money(annual_tax / periods_per_year)

    def _get_ytd_amount(
        self,
        *,
        employee: PayrollEmployee,
        tax_year: int,
        field: str,
    ) -> Decimal:
        """
        Get YTD amount from already-created pay stubs.
        """

        value = (
            PayStub.objects.filter(
                employee=employee,
                pay_run__pay_period__tax_year=tax_year,
                pay_run__status__in=[
                    "calculated",
                    "approved",
                    "posted",
                    "paid",
                ],
            )
            .aggregate(total=Sum(field))["total"]
            or ZERO
        )

        return self._money(value)

    def _override_money(self, override_value, calculated_value: Decimal) -> Decimal:
        """
        Use official/manual value when provided.
        """

        if override_value is None:
            return calculated_value

        return self._money(override_value)

    def _has_overrides(self, item: PayrollCalculationInput) -> bool:
        """
        Check if any official/manual value was provided.
        """

        return any(
            value is not None
            for value in [
                item.override_employee_cpp,
                item.override_employer_cpp,
                item.override_employee_cpp2,
                item.override_employer_cpp2,
                item.override_employee_ei,
                item.override_employer_ei,
                item.override_federal_income_tax,
                item.override_provincial_income_tax,
            ]
        )

    def _decimal_or_none(self, value) -> str | None:
        """
        Serialize optional decimal override for snapshots.
        """

        if value is None:
            return None

        return str(self._money(value))

    def _money(self, value: Decimal | int | float | str | None) -> Decimal:
        """
        Normalize money to cents.
        """

        if value is None:
            return ZERO

        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    
    # BUILD GROSS PAY ------------------------------------------
    def _build_gross_pay(
        self,
        *,
        item: PayrollCalculationInput,
        compensation_plan: PayrollCompensationPlan | None,
    ) -> dict:
        """
        Build gross pay components for monthly or hourly plans.
        """

        if not getattr(item, "include_regular_pay", True):
            return {
                "pay_type": (
                    compensation_plan.pay_type
                    if compensation_plan
                    else PayrollCompensationPlan.PAY_TYPE_MONTHLY_SALARY
                ),
                "hourly_rate": ZERO,
                "regular_hours": ZERO,
                "daily_overtime_hours": ZERO,
                "weekly_overtime_hours": ZERO,
                "double_time_hours": ZERO,
                "regular_pay": ZERO,
                "daily_overtime_pay": ZERO,
                "weekly_overtime_pay": ZERO,
                "double_time_pay": ZERO,
                "gross_salary": self._money(item.gross_salary),
            }
        
        if not compensation_plan:
            gross_salary = self._money(item.gross_salary)

            return {
                "pay_type": "monthly_salary",
                "hourly_rate": ZERO,
                "regular_hours": ZERO,
                "daily_overtime_hours": ZERO,
                "weekly_overtime_hours": ZERO,
                "double_time_hours": ZERO,
                "regular_pay": gross_salary,
                "daily_overtime_pay": ZERO,
                "weekly_overtime_pay": ZERO,
                "double_time_pay": ZERO,
                "gross_salary": gross_salary,
            }

        if compensation_plan.pay_type == PayrollCompensationPlan.PAY_TYPE_HOURLY:
            hourly_rate = self._money(compensation_plan.hourly_rate)

            regular_hours = self._money(item.regular_hours)
            daily_overtime_hours = self._money(item.daily_overtime_hours)
            weekly_overtime_hours = self._money(item.weekly_overtime_hours)
            double_time_hours = self._money(item.double_time_hours)

            if (
                regular_hours == ZERO
                and daily_overtime_hours == ZERO
                and weekly_overtime_hours == ZERO
                and double_time_hours == ZERO
                and compensation_plan.default_regular_hours_per_period > ZERO
            ):
                regular_hours = self._money(compensation_plan.default_regular_hours_per_period)

            regular_pay = self._money(hourly_rate * regular_hours)

            daily_overtime_pay = self._money(
                hourly_rate
                * compensation_plan.overtime_rate_multiplier
                * daily_overtime_hours
            )

            weekly_overtime_pay = self._money(
                hourly_rate
                * compensation_plan.overtime_rate_multiplier
                * weekly_overtime_hours
            )

            double_time_pay = self._money(
                hourly_rate
                * compensation_plan.double_time_rate_multiplier
                * double_time_hours
            )

            gross_salary = self._money(
                regular_pay
                + daily_overtime_pay
                + weekly_overtime_pay
                + double_time_pay
            )

            return {
                "pay_type": PayrollCompensationPlan.PAY_TYPE_HOURLY,
                "hourly_rate": hourly_rate,
                "regular_hours": regular_hours,
                "daily_overtime_hours": daily_overtime_hours,
                "weekly_overtime_hours": weekly_overtime_hours,
                "double_time_hours": double_time_hours,
                "regular_pay": regular_pay,
                "daily_overtime_pay": daily_overtime_pay,
                "weekly_overtime_pay": weekly_overtime_pay,
                "double_time_pay": double_time_pay,
                "gross_salary": gross_salary,
            }

        gross_salary = self._money(item.gross_salary)

        if gross_salary == ZERO:
            gross_salary = self._money(compensation_plan.monthly_salary)

        return {
            "pay_type": PayrollCompensationPlan.PAY_TYPE_MONTHLY_SALARY,
            "hourly_rate": ZERO,
            "regular_hours": ZERO,
            "daily_overtime_hours": ZERO,
            "weekly_overtime_hours": ZERO,
            "double_time_hours": ZERO,
            "regular_pay": gross_salary,
            "daily_overtime_pay": ZERO,
            "weekly_overtime_pay": ZERO,
            "double_time_pay": ZERO,
            "gross_salary": gross_salary,
        }

    def _split_cpp_components(
        self,
        *,
        employee_cpp: Decimal,
        current_pensionable: Decimal,
        ytd_pensionable: Decimal,
        config: PayrollYearConfig,
        tax_config: dict,
    ) -> dict:
        """
        Split CPP for T4127-oriented tax formulas.

        The first additional CPP portion is deductible from income.
        The base CPP portion is eligible for non-refundable tax credits.
        """

        employee_cpp = self._money(employee_cpp)

        if employee_cpp <= ZERO:
            return {
                "cpp_base": ZERO,
                "cpp_first_additional": ZERO,
            }

        cpp_base_rate = Decimal(str(tax_config.get("cpp_base_rate_employee", "0.0495")))
        cpp_first_additional_rate = Decimal(
            str(tax_config.get("cpp_first_additional_rate_employee", "0.0100"))
        )

        annual_max = config.cpp_max_pensionable_earnings or ZERO
        remaining_pensionable_room = max(annual_max - ytd_pensionable, ZERO)
        eligible_pensionable = min(current_pensionable, remaining_pensionable_room)

        prorated_exemption = self._money(
            (config.cpp_basic_exemption_annual or ZERO) / Decimal("12")
        )

        contributory_earnings = max(eligible_pensionable - prorated_exemption, ZERO)

        cpp_base = self._money(contributory_earnings * cpp_base_rate)
        cpp_first_additional = self._money(
            contributory_earnings * cpp_first_additional_rate
        )

        # Do not exceed actual CPP for the period.
        if cpp_base + cpp_first_additional > employee_cpp:
            cpp_first_additional = min(cpp_first_additional, employee_cpp)
            cpp_base = min(cpp_base, max(employee_cpp - cpp_first_additional, ZERO))

        return {
            "cpp_base": cpp_base,
            "cpp_first_additional": cpp_first_additional,
        }

    def _calculate_income_tax_v2(
        self,
        *,
        taxable_earnings: Decimal,
        employee_cpp: Decimal,
        employee_ei: Decimal,
        current_pensionable: Decimal,
        ytd_pensionable: Decimal,
        config: PayrollYearConfig,
        tax_config: dict,
        exempt: bool,
    ) -> Decimal:
        """
        T4127-oriented configurable income tax calculation.

        This is designed for regular salary/hourly payroll and must be
        verified against CRA PDOC before overrides are disabled.
        """

        if exempt:
            return ZERO

        if not tax_config:
            return ZERO

        periods_per_year = Decimal(str(tax_config.get("periods_per_year", 12)))
        brackets = tax_config.get("brackets", [])

        if not brackets:
            return ZERO

        cpp_split = self._split_cpp_components(
            employee_cpp=employee_cpp,
            current_pensionable=current_pensionable,
            ytd_pensionable=ytd_pensionable,
            config=config,
            tax_config=tax_config,
)

        cpp_base = cpp_split["cpp_base"]
        cpp_first_additional = cpp_split["cpp_first_additional"]

        period_income_deduction = ZERO

        if tax_config.get("deduct_cpp_first_additional_from_income", False):
            period_income_deduction += cpp_first_additional

        period_taxable_income = max(taxable_earnings - period_income_deduction, ZERO)
        annual_taxable_income = self._money(period_taxable_income * periods_per_year)

        annual_tax = self._calculate_annual_bracket_tax(
            annual_income=annual_taxable_income,
            brackets=brackets,
        )

        annual_tax -= self._calculate_tax_credits(
            tax_config=tax_config,
            employee_cpp_base=cpp_base,
            employee_ei=employee_ei,
            periods_per_year=periods_per_year,
            config=config,
        )

        annual_tax = self._apply_low_income_reduction(
            annual_tax=annual_tax,
            annual_taxable_income=annual_taxable_income,
            tax_config=tax_config,
        )

        annual_tax = max(annual_tax, ZERO)

        return self._money(annual_tax / periods_per_year)

    def _calculate_annual_bracket_tax(self, *, annual_income: Decimal, brackets: list) -> Decimal:
        """
        Calculate annual tax using T4127-style bracket constants when available.

        T4127 uses:
            annual tax = rate × annual income - constant

        The constant is K for federal tax and KP for provincial/territorial tax.
        If constants are missing, this method falls back to progressive bracket summing.
        """

        if not brackets:
            return ZERO

        has_constants = any("constant" in bracket for bracket in brackets)

        if has_constants:
            for bracket in brackets:
                up_to = bracket.get("up_to")

                if up_to is None:
                    rate = Decimal(str(bracket.get("rate", "0")))
                    constant = Decimal(str(bracket.get("constant", "0")))
                    return self._money((annual_income * rate) - constant)

                bracket_limit = Decimal(str(up_to))

                if annual_income <= bracket_limit:
                    rate = Decimal(str(bracket.get("rate", "0")))
                    constant = Decimal(str(bracket.get("constant", "0")))
                    return self._money((annual_income * rate) - constant)

            # Safety fallback to last bracket.
            last = brackets[-1]
            rate = Decimal(str(last.get("rate", "0")))
            constant = Decimal(str(last.get("constant", "0")))
            return self._money((annual_income * rate) - constant)

        # Legacy fallback: progressive bracket summing.
        annual_tax = ZERO
        previous_limit = ZERO

        for bracket in brackets:
            rate = Decimal(str(bracket.get("rate", "0")))
            up_to = bracket.get("up_to")

            if up_to is None:
                bracket_limit = annual_income
            else:
                bracket_limit = Decimal(str(up_to))

            taxable_in_bracket = max(
                min(annual_income, bracket_limit) - previous_limit,
                ZERO,
            )

            annual_tax += taxable_in_bracket * rate
            previous_limit = bracket_limit

            if annual_income <= bracket_limit:
                break

        return self._money(annual_tax)

    def _calculate_tax_credits(
        self,
        *,
        tax_config: dict,
        employee_cpp_base: Decimal,
        employee_ei: Decimal,
        periods_per_year: Decimal,
        config: PayrollYearConfig,
    ) -> Decimal:
        """
        Calculate non-refundable payroll tax credits.

        CPP base and EI credits are capped annually to avoid giving
        excess tax credits on high periodic earnings.
        """

        credit_rate = Decimal(str(tax_config.get("credit_rate", "0")))
        credits = tax_config.get("credits", {})

        claim_amount = Decimal(str(credits.get("basic_personal_amount", "0")))

        if credits.get("canada_employment_amount"):
            claim_amount += Decimal(str(credits.get("canada_employment_amount", "0")))

        annual_credit_base = claim_amount

        if credits.get("include_cpp_base_credit", False):
            annual_cpp_base_credit = self._money(
                employee_cpp_base * periods_per_year
            )

            max_annual_cpp_base_credit = self._get_max_annual_cpp_base_credit(
                config=config,
                tax_config=tax_config,
            )

            annual_credit_base += min(
                annual_cpp_base_credit,
                max_annual_cpp_base_credit,
            )

        if credits.get("include_ei_credit", False):
            annual_ei_credit = self._money(
                employee_ei * periods_per_year
            )

            max_annual_ei_credit = self._get_max_annual_ei_credit(
                config=config,
            )

            annual_credit_base += min(
                annual_ei_credit,
                max_annual_ei_credit,
            )

        return self._money(annual_credit_base * credit_rate)

    def _get_max_annual_cpp_base_credit(
        self,
        *,
        config: PayrollYearConfig,
        tax_config: dict,
    ) -> Decimal:
        """
        Return maximum annual base CPP amount eligible for tax credit.
        """

        explicit_cap = tax_config.get("max_annual_cpp_base_credit")

        if explicit_cap is not None:
            return self._money(explicit_cap)

        cpp_base_rate = Decimal(str(tax_config.get("cpp_base_rate_employee", "0.0495")))

        max_pensionable = config.cpp_max_pensionable_earnings or ZERO
        basic_exemption = config.cpp_basic_exemption_annual or ZERO

        contributory_max = max(max_pensionable - basic_exemption, ZERO)

        return self._money(contributory_max * cpp_base_rate)

    def _get_max_annual_ei_credit(
        self,
        *,
        config: PayrollYearConfig,
    ) -> Decimal:
        """
        Return maximum annual EI premium eligible for tax credit.
        """

        if not config.ei_enabled:
            return ZERO

        max_insurable = config.ei_max_insurable_earnings or ZERO
        ei_rate = config.ei_rate_employee or ZERO

        return self._money(max_insurable * ei_rate)

    def _apply_low_income_reduction(
        self,
        *,
        annual_tax: Decimal,
        annual_taxable_income: Decimal,
        tax_config: dict,
    ) -> Decimal:
        """
        Apply configurable low-income reduction when present.
        """

        reduction_config = tax_config.get("low_income_reduction", {})

        if not reduction_config.get("enabled", False):
            return annual_tax

        max_amount = Decimal(str(reduction_config.get("max_amount", "0")))
        threshold = Decimal(str(reduction_config.get("threshold", "0")))
        reduction_rate = Decimal(str(reduction_config.get("reduction_rate", "0")))

        if annual_taxable_income <= threshold:
            reduction = max_amount
        else:
            reduction = max_amount - (
                (annual_taxable_income - threshold) * reduction_rate
            )

        reduction = max(reduction, ZERO)

        return self._money(max(annual_tax - reduction, ZERO))