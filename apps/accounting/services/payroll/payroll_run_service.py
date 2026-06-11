# apps/accounting/services/payroll/payroll_run_service.py

from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from apps.accounting.models import (
    PayrollYearConfig,
    PayrollEmployee,
    PayrollCompensationPlan,
    PayPeriod,
    PayRun,
    PayStub,
    PayrollWorkSummary,
)
from apps.accounting.services.payroll.calculation_engine import (
    PayrollCalculationEngine,
)
from apps.accounting.services.payroll.run_number import generate_pay_run_number
from apps.accounting.services.payroll.schemas import PayrollCalculationInput
from apps.accounting.services.payroll.remittance_service import PayrollRemittanceService
from apps.accounting.services.payroll.vacation_balance_service import (
    VacationPayBalanceService,
)

ZERO = Decimal("0.00")


class PayrollRunError(Exception):
    """
    Raised when payroll run workflow fails.
    """
    pass


class PayrollRunService:
    """
    Creates and calculates payroll runs.
    """

    calculation_engine = PayrollCalculationEngine()
    remittance_service = PayrollRemittanceService()

    def create_monthly_pay_run(
        self,
        *,
        pay_period: PayPeriod,
        payroll_year_config: PayrollYearConfig,
        employees: list[PayrollEmployee],
        actual_paid_by_employee_id: dict[int, Decimal] | None = None,
        payment_note_by_employee_id: dict[int, str] | None = None,
        override_by_employee_id: dict[int, dict] | None = None,
        hourly_input_by_employee_id: dict[int, dict] | None = None,
        created_by=None,
    ) -> PayRun:
        """
        Create and calculate one pay run.
        Supports both monthly salary and hourly employees.
        """

        if pay_period.status not in {
            PayPeriod.STATUS_OPEN,
            PayPeriod.STATUS_PROCESSING,
        }:
            raise PayrollRunError("Pay period is not open for payroll.")

        if pay_period.tax_year != payroll_year_config.year:
            raise PayrollRunError("Pay period tax year does not match payroll config.")

        if not employees:
            raise PayrollRunError("At least one employee is required.")

        existing_stub_exists = (
            PayStub.objects.filter(
                employee__in=employees,
                pay_run__pay_period=pay_period,
            )
            .exclude(
                pay_run__status=PayRun.STATUS_VOID,
            )
            .exists()
        )

        if existing_stub_exists:
            raise PayrollRunError(
                "A non-void pay run already exists for one or more selected employees in this pay period."
            )

        actual_paid_by_employee_id = actual_paid_by_employee_id or {}
        payment_note_by_employee_id = payment_note_by_employee_id or {}
        override_by_employee_id = override_by_employee_id or {}
        hourly_input_by_employee_id = hourly_input_by_employee_id or {}

        with db_transaction.atomic():
            pay_run = PayRun.objects.create(
                pay_period=pay_period,
                payroll_year_config=payroll_year_config,
                run_number=generate_pay_run_number(),
                run_date=timezone.localdate(),
                description=f"Payroll run for {pay_period.code}",
                status=PayRun.STATUS_DRAFT,
                created_by=created_by,
            )

            for employee in employees:
                plan = self._get_active_compensation_plan(
                    employee=employee,
                    period_end=pay_period.end_date,
                )

                gross_salary = self._resolve_base_gross_salary(
                    compensation_plan=plan,
                )

                actual_paid = Decimal(
                    str(actual_paid_by_employee_id.get(employee.id, ZERO))
                )

                overrides = override_by_employee_id.get(employee.id, {}) or {}

                hourly_input = hourly_input_by_employee_id.get(employee.id, {}) or {}

                work_summary = self._get_approved_work_summary(
                    employee=employee,
                    pay_period=pay_period,
                )

                if work_summary and not hourly_input:
                    hourly_input = {
                        "regular_hours": work_summary.regular_hours,
                        "daily_overtime_hours": work_summary.daily_overtime_hours,
                        "weekly_overtime_hours": work_summary.weekly_overtime_hours,
                        "double_time_hours": work_summary.double_time_hours,
                        "work_summary_id": work_summary.id,
                    }

                item = PayrollCalculationInput(
                    employee_id=employee.id,
                    compensation_plan_id=plan.id if plan else None,
                    gross_salary=gross_salary,
                    actual_paid=actual_paid,
                    include_regular_pay=True,
                    pay_period_start=pay_period.start_date,
                    pay_period_end=pay_period.end_date,
                    pay_date=pay_period.pay_date,
                    tax_year=pay_period.tax_year,
                    payment_note=payment_note_by_employee_id.get(
                        employee.id,
                        f"TownLIT Payroll - {pay_period.end_date.strftime('%B %Y')}",
                    ),
                    override_employee_cpp=overrides.get("employee_cpp"),
                    override_employer_cpp=overrides.get("employer_cpp"),
                    override_employee_cpp2=overrides.get("employee_cpp2"),
                    override_employer_cpp2=overrides.get("employer_cpp2"),
                    override_employee_ei=overrides.get("employee_ei"),
                    override_employer_ei=overrides.get("employer_ei"),
                    override_federal_income_tax=overrides.get("federal_income_tax"),
                    override_provincial_income_tax=overrides.get("provincial_income_tax"),
                    override_source=overrides.get("override_source", ""),
                    override_note=overrides.get("override_note", ""),
                    regular_hours=hourly_input.get("regular_hours", ZERO),
                    daily_overtime_hours=hourly_input.get(
                        "daily_overtime_hours",
                        ZERO,
                    ),
                    weekly_overtime_hours=hourly_input.get(
                        "weekly_overtime_hours",
                        ZERO,
                    ),
                    double_time_hours=hourly_input.get("double_time_hours", ZERO),
                    work_summary_id=hourly_input.get("work_summary_id"),
                )

                result = self.calculation_engine.calculate(
                    item=item,
                    config=payroll_year_config,
                )

                self._create_pay_stub(
                    pay_run=pay_run,
                    employee=employee,
                    compensation_plan=plan,
                    result=result,
                )

            self._refresh_pay_run_totals(pay_run=pay_run)

            pay_run.status = PayRun.STATUS_CALCULATED
            pay_run.save(update_fields=["status", "updated_at"])

            return pay_run

    def approve_pay_run(self, *, pay_run: PayRun, approved_by=None) -> PayRun:
        """
        Approve a calculated pay run.
        """

        if pay_run.status != PayRun.STATUS_CALCULATED:
            raise PayrollRunError("Only calculated pay runs can be approved.")

        if not pay_run.pay_stubs.exists():
            raise PayrollRunError("Pay run has no pay stubs.")

        pay_run.status = PayRun.STATUS_APPROVED
        pay_run.approved_by = approved_by
        pay_run.approved_at = timezone.now()
        pay_run.save(
            update_fields=[
                "status",
                "approved_by",
                "approved_at",
                "updated_at",
            ]
        )

        return pay_run

    def create_remittance_for_pay_run(
        self,
        *,
        pay_run: PayRun,
        due_date=None,
    ):
        """
        Create CRA payroll remittance record for a pay run.
        """

        if pay_run.status not in {
            PayRun.STATUS_APPROVED,
            PayRun.STATUS_POSTED,
            PayRun.STATUS_PAID,
        }:
            raise PayrollRunError("Pay run must be approved before remittance.")

        return self.remittance_service.create_for_pay_run(
            pay_run=pay_run,
            due_date=due_date,
        )

    def _resolve_base_gross_salary(
        self,
        *,
        compensation_plan: PayrollCompensationPlan | None,
    ) -> Decimal:
        """
        Resolve base gross salary input.

        For hourly plans, gross pay is calculated by the calculation engine
        from hours and hourly rate, so this can safely be zero.
        """

        if not compensation_plan:
            return ZERO

        if compensation_plan.pay_type == PayrollCompensationPlan.PAY_TYPE_HOURLY:
            return ZERO

        return compensation_plan.monthly_salary or ZERO

    def _get_active_compensation_plan(
        self,
        *,
        employee: PayrollEmployee,
        period_end,
    ) -> PayrollCompensationPlan | None:
        """
        Resolve active compensation plan for the pay period.
        """

        from django.db.models import Q

        return (
            PayrollCompensationPlan.objects.filter(
                employee=employee,
                status=PayrollCompensationPlan.STATUS_ACTIVE,
                effective_from__lte=period_end,
            )
            .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=period_end))
            .order_by("-effective_from", "-id")
            .first()
        )

    def _create_pay_stub(
        self,
        *,
        pay_run: PayRun,
        employee: PayrollEmployee,
        compensation_plan: PayrollCompensationPlan | None,
        result,
    ) -> PayStub:
        """
        Persist one calculated pay stub.
        """

        return PayStub.objects.create(
            pay_run=pay_run,
            employee=employee,
            compensation_plan=compensation_plan,

            # Pay type / hourly details
            pay_type=result.pay_type,
            hourly_rate=result.hourly_rate,
            regular_hours=result.regular_hours,
            daily_overtime_hours=result.daily_overtime_hours,
            weekly_overtime_hours=result.weekly_overtime_hours,
            double_time_hours=result.double_time_hours,
            regular_pay=result.regular_pay,
            daily_overtime_pay=result.daily_overtime_pay,
            weekly_overtime_pay=result.weekly_overtime_pay,
            double_time_pay=result.double_time_pay,
            work_summary_id=result.work_summary_id,

            # Earnings
            gross_salary=result.gross_salary,
            vacation_pay_earned=result.vacation_pay_earned,
            vacation_pay_paid=result.vacation_pay_paid,
            sick_pay_paid=result.sick_pay_paid,
            taxable_benefits=result.taxable_benefits,
            pensionable_earnings=result.pensionable_earnings,
            insurable_earnings=result.insurable_earnings,
            taxable_earnings=result.taxable_earnings,

            # Employee deductions
            employee_cpp=result.employee_cpp,
            employee_cpp2=result.employee_cpp2,
            employee_ei=result.employee_ei,
            federal_income_tax=result.federal_income_tax,
            provincial_income_tax=result.provincial_income_tax,
            other_employee_deductions=result.other_employee_deductions,
            total_employee_deductions=result.total_employee_deductions,

            # Employer contributions
            employer_cpp=result.employer_cpp,
            employer_cpp2=result.employer_cpp2,
            employer_ei=result.employer_ei,
            other_employer_contributions=result.other_employer_contributions,
            total_employer_contributions=result.total_employer_contributions,

            # Net pay / payment
            net_pay=result.net_pay,
            actual_paid=result.actual_paid,
            net_salary_payable=result.net_salary_payable,
            total_remittance_due=result.total_remittance_due,
            payment_reference=result.payment_reference,
            payment_note=result.payment_note,

            # Audit
            calculation_snapshot=result.calculation_snapshot,
        )

    def _refresh_pay_run_totals(self, *, pay_run: PayRun) -> PayRun:
        """
        Refresh aggregate totals from pay stubs.
        """

        totals = {
            "total_gross_pay": ZERO,
            "total_employee_deductions": ZERO,
            "total_employer_contributions": ZERO,
            "total_net_pay": ZERO,
            "total_actual_paid": ZERO,
            "total_salary_payable": ZERO,
            "total_remittance_due": ZERO,
        }

        for stub in pay_run.pay_stubs.all():
            totals["total_gross_pay"] += stub.gross_salary or ZERO
            totals["total_employee_deductions"] += stub.total_employee_deductions or ZERO
            totals["total_employer_contributions"] += stub.total_employer_contributions or ZERO
            totals["total_net_pay"] += stub.net_pay or ZERO
            totals["total_actual_paid"] += stub.actual_paid or ZERO
            totals["total_salary_payable"] += stub.net_salary_payable or ZERO
            totals["total_remittance_due"] += stub.total_remittance_due or ZERO

        for field, value in totals.items():
            setattr(pay_run, field, value)

        pay_run.save(update_fields=[*totals.keys(), "updated_at"])

        return pay_run

    def _get_approved_work_summary(
        self,
        *,
        employee: PayrollEmployee,
        pay_period: PayPeriod,
    ):
        """
        Resolve approved work summary from future attendance/time-clock systems.
        """

        return (
            PayrollWorkSummary.objects.filter(
                employee=employee,
                pay_period=pay_period,
                status=PayrollWorkSummary.STATUS_APPROVED,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        

    def create_vacation_pay_run(
        self,
        *,
        pay_period: PayPeriod,
        payroll_year_config: PayrollYearConfig,
        employee: PayrollEmployee,
        vacation_pay_amount: Decimal,
        payment_note: str = "",
        override_values: dict | None = None,
        created_by=None,
    ) -> PayRun:
        """
        Create a standalone vacation pay run.

        Vacation pay is taxable and goes through payroll deductions.
        Actual bank payment is recorded later through Record Salary Payment.
        """

        if pay_period.status not in {
            PayPeriod.STATUS_OPEN,
            PayPeriod.STATUS_PROCESSING,
        }:
            raise PayrollRunError("Pay period is not open for payroll.")

        if pay_period.tax_year != payroll_year_config.year:
            raise PayrollRunError("Pay period tax year does not match payroll config.")

        vacation_pay_amount = Decimal(str(vacation_pay_amount)).quantize(Decimal("0.01"))

        if vacation_pay_amount <= ZERO:
            raise PayrollRunError("Vacation pay amount must be greater than zero.")

        overrides = override_values or {}

        with db_transaction.atomic():
            # Lock employee row to prevent double-submit/race duplicate vacation payouts.
            employee = PayrollEmployee.objects.select_for_update().get(id=employee.id)

            balance_service = VacationPayBalanceService()

            existing_run = balance_service.get_existing_vacation_pay_run_for_period(
                employee=employee,
                pay_period=pay_period,
            )

            if existing_run:
                raise PayrollRunError(
                    f"A vacation pay run already exists for this employee and pay period: {existing_run.run_number}. "
                    "Void the existing run before creating another one for the same period."
                )

            balance = balance_service.get_balance(
                employee=employee,
                tax_year=pay_period.tax_year,
            )

            available_balance = Decimal(str(balance["balance"])).quantize(Decimal("0.01"))

            if available_balance <= ZERO:
                raise PayrollRunError("There is no available vacation pay balance for this employee.")

            if vacation_pay_amount != available_balance:
                raise PayrollRunError(
                    f"Vacation pay run must use the full available vacation balance ({available_balance}). "
                    "Partial vacation pay runs are not allowed."
                )

            plan = self._get_active_compensation_plan(
                employee=employee,
                period_end=pay_period.end_date,
            )

            pay_run = PayRun.objects.create(
                pay_period=pay_period,
                payroll_year_config=payroll_year_config,
                run_number=generate_pay_run_number(),
                run_date=timezone.localdate(),
                description=f"Vacation pay run for {employee.display_name} - {pay_period.code}",
                status=PayRun.STATUS_DRAFT,
                created_by=created_by,
            )

            item = PayrollCalculationInput(
                employee_id=employee.id,
                compensation_plan_id=plan.id if plan else None,
                gross_salary=ZERO,
                actual_paid=ZERO,
                include_regular_pay=False,
                vacation_pay_paid=vacation_pay_amount,
                pay_period_start=pay_period.start_date,
                pay_period_end=pay_period.end_date,
                pay_date=pay_period.pay_date,
                tax_year=pay_period.tax_year,
                payment_note=payment_note or f"TownLIT Vacation Pay - {pay_period.end_date.strftime('%B %Y')}",
                override_employee_cpp=overrides.get("employee_cpp"),
                override_employer_cpp=overrides.get("employer_cpp"),
                override_employee_cpp2=overrides.get("employee_cpp2"),
                override_employer_cpp2=overrides.get("employer_cpp2"),
                override_employee_ei=overrides.get("employee_ei"),
                override_employer_ei=overrides.get("employer_ei"),
                override_federal_income_tax=overrides.get("federal_income_tax"),
                override_provincial_income_tax=overrides.get("provincial_income_tax"),
                override_source=overrides.get("override_source", ""),
                override_note=overrides.get("override_note", ""),
            )

            result = self.calculation_engine.calculate(
                item=item,
                config=payroll_year_config,
            )

            self._create_pay_stub(
                pay_run=pay_run,
                employee=employee,
                compensation_plan=plan,
                result=result,
            )

            self._refresh_pay_run_totals(pay_run=pay_run)

            pay_run.status = PayRun.STATUS_CALCULATED
            pay_run.save(update_fields=["status", "updated_at"])

            return pay_run