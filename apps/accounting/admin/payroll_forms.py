# apps/accounting/admin/payroll_forms.py

from decimal import Decimal
from django import forms
from django.utils import timezone

from apps.accounting.services.account_lookup import AccountCodes
from apps.accounting.models import (
    PayrollYearConfig,
    PayrollEmployee,
    PayPeriod,
)

# -----------------------------------------------------------------
# Payroll Employee Choice Field
# -----------------------------------------------------------------
class PayrollEmployeeChoiceField(forms.ModelChoiceField):
    """
    Display employee with active compensation plan pay type.
    """

    def label_from_instance(self, obj):
        plan = (
            obj.compensation_plans.filter(status="active")
            .order_by("-effective_from", "-id")
            .first()
        )

        if not plan:
            return f"{obj.display_name} — no active compensation plan"

        if plan.pay_type == "hourly":
            return f"{obj.display_name} — Hourly (${plan.hourly_rate}/hr)"

        return f"{obj.display_name} — Monthly salary (${plan.monthly_salary}/month)"
    
# -----------------------------------------------------------------
# Create Pay Run Admin Form
# -----------------------------------------------------------------
class CreatePayRunAdminForm(forms.Form):
    """
    Admin form for creating one employee pay run.
    """

    pay_period = forms.ModelChoiceField(
        queryset=PayPeriod.objects.order_by("-start_date"),
        required=True,
    )

    payroll_year_config = forms.ModelChoiceField(
        queryset=PayrollYearConfig.objects.filter(is_active=True).order_by("-year"),
        required=True,
    )

    employee = PayrollEmployeeChoiceField(
        queryset=PayrollEmployee.objects.filter(is_active=True).order_by("display_name"),
        required=True,
    )

    payment_note = forms.CharField(
        max_length=255,
        required=False,
        initial="TownLIT Payroll - May 2026",
    )

    use_manual_overrides = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Use official CRA/PDOC values entered below.",
    )

    employee_cpp = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_cpp = forms.DecimalField(max_digits=14, decimal_places=2, required=False)

    employee_cpp2 = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_cpp2 = forms.DecimalField(max_digits=14, decimal_places=2, required=False)

    employee_ei = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_ei = forms.DecimalField(max_digits=14, decimal_places=2, required=False)

    federal_income_tax = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    provincial_income_tax = forms.DecimalField(max_digits=14, decimal_places=2, required=False)

    override_source = forms.CharField(
        max_length=255,
        required=False,
        initial="CRA PDOC",
    )

    override_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        required=False,
        initial="",
        help_text="Optional. Use this only when manual CRA/PDOC override values are entered.",
    )

    show_hourly_fields = forms.BooleanField(
        required=False,
        initial=False,
        help_text="Show hourly input fields. Use this only for hourly employees or manual hourly adjustments.",
    )

    regular_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        help_text="For hourly employees only. Leave 0 for monthly salary employees.",
    )

    daily_overtime_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        help_text="Hourly employees only. Usually 1.5x daily overtime.",
    )

    weekly_overtime_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        help_text="Hourly employees only. Usually 1.5x weekly overtime.",
    )

    double_time_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        help_text="Hourly employees only. Usually 2x daily overtime.",
    )
    
    def clean(self):
        """
        Validate payroll period and config alignment.
        """

        cleaned_data = super().clean()

        pay_period = cleaned_data.get("pay_period")
        config = cleaned_data.get("payroll_year_config")

        if pay_period and config and pay_period.tax_year != config.year:
            raise forms.ValidationError(
                "Pay period tax year must match payroll year config."
            )

        return cleaned_data
    
    
# -----------------------------------------------------------------
# Record Salary Payment Admin Form
# -----------------------------------------------------------------
class RecordSalaryPaymentAdminForm(forms.Form):
    """
    Admin form for recording actual salary payment.
    """

    paid_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Paid on",
    )

    payment_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Payment amount",
        help_text=(
            "Default is the remaining net pay after CPP/EI/tax deductions. "
            "You may enter a smaller amount for a partial payment."
        ),
    )

    bank_account_code = forms.CharField(
        max_length=20,
        initial=AccountCodes.BANK,
        label="Bank account code",
    )

    payment_method = forms.ChoiceField(
        choices=(
            ("e_transfer", "E-Transfer"),
            ("direct_deposit", "Direct Deposit"),
            ("cheque", "Cheque"),
            ("bank_transfer", "Bank Transfer"),
            ("other", "Other"),
        ),
        initial="e_transfer",
        label="Payment method",
    )

    payment_reference = forms.CharField(
        max_length=255,
        required=False,
        label="Payment reference",
        help_text="Example: E-Transfer Payroll - May 2026",
    )

# -----------------------------------------------------------------
# Record Payroll Remittance Payment Admin Form
# -----------------------------------------------------------------
class RecordPayrollRemittancePaymentAdminForm(forms.Form):
    """
    Admin form for recording CRA payroll remittance payment.
    """

    paid_on = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
    )

    bank_account_code = forms.CharField(
        max_length=20,
        initial=AccountCodes.BANK,
        help_text="Ledger account code for the bank account.",
    )

    payment_reference = forms.CharField(
        max_length=255,
        required=True,
        initial="CRA Payroll Remittance - May 2026",
    )
    

# -----------------------------------------------------------------
# Create Vacation Pay Run Admin Form
# -----------------------------------------------------------------
class CreateVacationPayRunAdminForm(forms.Form):
    """
    Admin form for creating an independent vacation pay run.
    """

    pay_period = forms.ModelChoiceField(
        queryset=PayPeriod.objects.filter(status__in=["open", "processing"]).order_by("-start_date"),
        label="Pay period",
    )

    payroll_year_config = forms.ModelChoiceField(
        queryset=PayrollYearConfig.objects.filter(is_active=True).order_by("-year", "province"),
        label="Payroll year config",
    )

    employee = forms.ModelChoiceField(
        queryset=PayrollEmployee.objects.filter(is_active=True).order_by("display_name"),
        label="Employee",
    )

    vacation_pay_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Vacation pay amount",
        help_text=(
            "This field is auto-filled with the employee's full available vacation balance. "
            "Partial vacation pay runs are not allowed."
        ),
        widget=forms.NumberInput(
            attrs={
                "readonly": "readonly",
                "step": "0.01",
            }
        ),
    )

    payment_note = forms.CharField(
        max_length=255,
        required=False,
        initial="TownLIT Vacation Pay",
        label="Payment note",
    )

    use_manual_overrides = forms.BooleanField(
        required=False,
        initial=False,
        label="Use manual overrides",
        help_text="Use only when matching official CRA PDOC reviewed values.",
    )

    employee_cpp = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_cpp = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employee_cpp2 = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_cpp2 = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employee_ei = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    employer_ei = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    federal_income_tax = forms.DecimalField(max_digits=14, decimal_places=2, required=False)
    provincial_income_tax = forms.DecimalField(max_digits=14, decimal_places=2, required=False)

    override_source = forms.CharField(
        max_length=100,
        required=False,
        initial="CRA PDOC",
    )

    override_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
    )
    
    def clean(self):
        """
        Require full available vacation balance.
        """

        cleaned_data = super().clean()

        employee = cleaned_data.get("employee")
        pay_period = cleaned_data.get("pay_period")
        amount = cleaned_data.get("vacation_pay_amount")

        if not employee or not pay_period or not amount:
            return cleaned_data

        from apps.accounting.services.payroll.vacation_balance_service import (
            VacationPayBalanceService,
        )

        balance = VacationPayBalanceService().get_balance(
            employee=employee,
            tax_year=pay_period.tax_year,
        )

        available_balance = Decimal(str(balance["balance"])).quantize(Decimal("0.01"))

        if available_balance <= Decimal("0.00"):
            raise forms.ValidationError(
                "There is no available vacation pay balance for this employee."
            )

        if amount != available_balance:
            raise forms.ValidationError(
                f"Vacation pay run must use the full available balance ({available_balance}). "
                "Partial vacation pay runs are not allowed."
            )

        return cleaned_data