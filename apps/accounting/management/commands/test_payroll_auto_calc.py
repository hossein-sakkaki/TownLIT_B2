# apps/accounting/management/commands/test_payroll_auto_calc.py

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.accounting.models import (
    PayrollEmployee,
    PayrollYearConfig,
    PayrollCompensationPlan,
)
from apps.accounting.services.payroll.calculation_engine import PayrollCalculationEngine
from apps.accounting.services.payroll.schemas import PayrollCalculationInput


class Command(BaseCommand):
    help = "Test payroll auto calculation without creating pay runs."

    def add_arguments(self, parser):
        parser.add_argument("--employee-id", type=int, required=True)
        parser.add_argument("--gross", type=Decimal, required=True)
        parser.add_argument("--actual-paid", type=Decimal, default=Decimal("0.00"))

    def handle(self, *args, **options):
        employee = PayrollEmployee.objects.get(id=options["employee_id"])
        config = PayrollYearConfig.objects.get(year=2026, province="BC")

        plan = (
            PayrollCompensationPlan.objects.filter(
                employee=employee,
                status=PayrollCompensationPlan.STATUS_ACTIVE,
            )
            .order_by("-effective_from", "-id")
            .first()
        )

        result = PayrollCalculationEngine().calculate(
            item=PayrollCalculationInput(
                employee_id=employee.id,
                compensation_plan_id=plan.id if plan else None,
                gross_salary=options["gross"],
                actual_paid=options["actual_paid"],
                pay_period_start=date(2026, 5, 1),
                pay_period_end=date(2026, 5, 31),
                pay_date=date(2026, 6, 1),
                tax_year=2026,
            ),
            config=config,
        )

        self.stdout.write(f"Gross: {result.gross_salary}")
        self.stdout.write(f"Employee CPP: {result.employee_cpp}")
        self.stdout.write(f"Employer CPP: {result.employer_cpp}")
        self.stdout.write(f"Employee CPP2: {result.employee_cpp2}")
        self.stdout.write(f"Employer CPP2: {result.employer_cpp2}")
        self.stdout.write(f"Employee EI: {result.employee_ei}")
        self.stdout.write(f"Employer EI: {result.employer_ei}")
        self.stdout.write(f"Federal tax: {result.federal_income_tax}")
        self.stdout.write(f"Provincial tax: {result.provincial_income_tax}")
        self.stdout.write(f"Total deductions: {result.total_employee_deductions}")
        self.stdout.write(f"Net pay: {result.net_pay}")
        self.stdout.write(f"Remittance due: {result.total_remittance_due}")
        
        
        
# docker compose exec backend python manage.py test_payroll_auto_calc --employee-id 1 --gross 2500.00 --actual-paid 1600.00