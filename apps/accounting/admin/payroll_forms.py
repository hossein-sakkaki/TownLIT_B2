# apps/accounting/admin/payroll_forms.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.accounting.models import (
    BankAccount,
    PayPeriod,
    PayrollCompensationPlan,
    PayrollEmployee,
    PayrollYearConfig,
)


class PayrollEmployeeChoiceField(forms.ModelChoiceField):
    """Show the employee together with the current pay setup."""

    def label_from_instance(self, obj):
        plan = (
            obj.compensation_plans.filter(
                status=PayrollCompensationPlan.STATUS_ACTIVE,
            )
            .order_by("-effective_from", "-id")
            .first()
        )

        if not plan:
            return f"{obj.display_name} — payroll setup required"

        if plan.pay_type == PayrollCompensationPlan.PAY_TYPE_HOURLY:
            return f"{obj.display_name} — Hourly (${plan.hourly_rate}/hr)"

        return f"{obj.display_name} — Monthly salary (${plan.monthly_salary}/month)"


class ActiveBankAccountChoiceField(forms.ModelChoiceField):
    """Human-friendly bank account selector for payroll payments."""

    def label_from_instance(self, obj):
        institution = obj.institution_name_snapshot or obj.institution.name
        masked = obj.account_number_masked or "account number not stored"
        ledger_code = obj.ledger_account.code
        return f"{obj.name} — {institution} — {masked} — GL {ledger_code}"


def _active_bank_accounts():
    return (
        BankAccount.objects.filter(
            is_active=True,
            status=BankAccount.STATUS_ACTIVE,
            ledger_account__is_active=True,
            ledger_account__allows_posting=True,
        )
        .select_related("institution", "ledger_account")
        .order_by("-is_primary", "name", "code")
    )


def _active_payroll_config_for_period(pay_period):
    if not pay_period:
        return None

    return PayrollYearConfig.objects.filter(
        year=pay_period.tax_year,
        is_active=True,
    ).first()


def _active_plan_for_period(employee, pay_period):
    if not employee or not pay_period:
        return None

    return (
        PayrollCompensationPlan.objects.filter(
            employee=employee,
            status=PayrollCompensationPlan.STATUS_ACTIVE,
            effective_from__lte=pay_period.end_date,
        )
        .filter(
            Q(effective_to__isnull=True)
            | Q(effective_to__gte=pay_period.start_date)
        )
        .order_by("-effective_from", "-id")
        .first()
    )


class CreatePayRunAdminForm(forms.Form):
    """Create one normal payroll run with technical setup resolved automatically."""

    pay_period = forms.ModelChoiceField(
        queryset=PayPeriod.objects.none(),
        required=True,
        label="Pay period",
    )

    # Kept in the form contract for the existing admin service call, but hidden
    # from accountants. The correct active config is resolved from tax_year.
    payroll_year_config = forms.ModelChoiceField(
        queryset=PayrollYearConfig.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )

    employee = PayrollEmployeeChoiceField(
        queryset=PayrollEmployee.objects.none(),
        required=True,
        label="Employee",
    )

    payment_note = forms.CharField(
        max_length=255,
        required=False,
        initial="TownLIT Payroll",
        label="Payroll note",
        help_text="Optional reference shown on payroll records and payment workflow.",
    )

    show_hourly_fields = forms.BooleanField(
        required=False,
        initial=False,
        label="Enter hourly work manually",
        help_text="Use only for hourly payroll when work hours are not already available.",
    )

    regular_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        label="Regular hours",
    )

    daily_overtime_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        label="Daily overtime hours",
    )

    weekly_overtime_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        label="Weekly overtime hours",
    )

    double_time_hours = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        initial=Decimal("0.00"),
        min_value=Decimal("0.00"),
        label="Double-time hours",
    )

    use_manual_overrides = forms.BooleanField(
        required=False,
        initial=False,
        label="Use reviewed CRA / PDOC overrides",
        help_text="Leave off for normal automatic payroll calculation.",
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
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        periods = PayPeriod.objects.filter(
            status__in=(PayPeriod.STATUS_OPEN, PayPeriod.STATUS_PROCESSING),
        ).select_related("schedule").order_by("-pay_date", "-start_date")

        ready_employees = (
            PayrollEmployee.objects.filter(
                is_active=True,
                compensation_plans__status=PayrollCompensationPlan.STATUS_ACTIVE,
            )
            .distinct()
            .order_by("display_name")
        )

        self.fields["pay_period"].queryset = periods
        self.fields["employee"].queryset = ready_employees
        self.fields["payroll_year_config"].queryset = PayrollYearConfig.objects.filter(
            is_active=True,
        ).order_by("-year")

        if not self.is_bound:
            initial_period = None
            initial_period_value = self.initial.get("pay_period")

            if initial_period_value:
                try:
                    initial_period = periods.get(pk=initial_period_value)
                except (PayPeriod.DoesNotExist, TypeError, ValueError):
                    initial_period = None

            if initial_period is None:
                initial_period = periods.first()

            if initial_period:
                self.initial["pay_period"] = initial_period.pk
                config = _active_payroll_config_for_period(initial_period)
                if config:
                    self.initial["payroll_year_config"] = config.pk

    def clean(self):
        cleaned_data = super().clean()

        pay_period = cleaned_data.get("pay_period")
        employee = cleaned_data.get("employee")

        if not pay_period:
            return cleaned_data

        config = _active_payroll_config_for_period(pay_period)
        if not config:
            raise forms.ValidationError(
                f"No active payroll configuration exists for tax year {pay_period.tax_year}."
            )

        cleaned_data["payroll_year_config"] = config

        if employee and not _active_plan_for_period(employee, pay_period):
            raise forms.ValidationError(
                f"{employee.display_name} does not have an active compensation plan "
                f"covering this pay period. Update the employee payroll setup first."
            )

        if not (cleaned_data.get("payment_note") or "").strip():
            cleaned_data["payment_note"] = (
                f"TownLIT Payroll - {pay_period.end_date.strftime('%B %Y')}"
            )

        return cleaned_data


class RecordSalaryPaymentAdminForm(forms.Form):
    """Record an actual full or partial salary payment."""

    paid_on = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Paid on",
    )

    payment_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Payment amount",
        help_text="You may enter a smaller amount for a partial payment.",
    )

    # Field name is preserved for compatibility with existing templates/admin code.
    # Its value is now a real BankAccount instead of a raw GL code.
    bank_account_code = ActiveBankAccountChoiceField(
        queryset=BankAccount.objects.none(),
        label="Pay from bank account",
        empty_label=None,
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
        help_text="Bank confirmation, transfer reference, or payroll payment note.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        banks = _active_bank_accounts()
        self.fields["bank_account_code"].queryset = banks

        if not self.is_bound:
            preferred = banks.filter(is_primary=True).first() or banks.first()
            if preferred:
                self.initial.setdefault("bank_account_code", preferred.pk)


class RecordPayrollRemittancePaymentAdminForm(forms.Form):
    """Record an actual CRA payroll remittance payment."""

    paid_on = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={"type": "date"}),
        initial=timezone.localdate,
        label="Paid on",
    )

    bank_account_code = ActiveBankAccountChoiceField(
        queryset=BankAccount.objects.none(),
        label="Pay from bank account",
        empty_label=None,
    )

    payment_reference = forms.CharField(
        max_length=255,
        required=True,
        initial="CRA Payroll Remittance",
        label="Payment reference",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        banks = _active_bank_accounts()
        self.fields["bank_account_code"].queryset = banks

        if not self.is_bound:
            preferred = banks.filter(is_primary=True).first() or banks.first()
            if preferred:
                self.initial.setdefault("bank_account_code", preferred.pk)


class CreateVacationPayRunAdminForm(forms.Form):
    """Create a standalone full-balance vacation pay run."""

    pay_period = forms.ModelChoiceField(
        queryset=PayPeriod.objects.none(),
        label="Pay period",
    )

    payroll_year_config = forms.ModelChoiceField(
        queryset=PayrollYearConfig.objects.none(),
        required=False,
        widget=forms.HiddenInput(),
    )

    employee = PayrollEmployeeChoiceField(
        queryset=PayrollEmployee.objects.none(),
        label="Employee",
    )

    vacation_pay_amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Vacation pay amount",
        help_text="Automatically filled with the employee's full available balance.",
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
        label="Use reviewed CRA / PDOC overrides",
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        periods = PayPeriod.objects.filter(
            status__in=(PayPeriod.STATUS_OPEN, PayPeriod.STATUS_PROCESSING),
        ).select_related("schedule").order_by("-pay_date", "-start_date")

        ready_employees = (
            PayrollEmployee.objects.filter(
                is_active=True,
                compensation_plans__status=PayrollCompensationPlan.STATUS_ACTIVE,
            )
            .distinct()
            .order_by("display_name")
        )

        self.fields["pay_period"].queryset = periods
        self.fields["employee"].queryset = ready_employees
        self.fields["payroll_year_config"].queryset = PayrollYearConfig.objects.filter(
            is_active=True,
        ).order_by("-year")

        if not self.is_bound:
            initial_period_value = self.initial.get("pay_period")
            initial_period = None

            if initial_period_value:
                try:
                    initial_period = periods.get(pk=initial_period_value)
                except (PayPeriod.DoesNotExist, TypeError, ValueError):
                    initial_period = None

            if initial_period is None:
                initial_period = periods.first()

            if initial_period:
                self.initial["pay_period"] = initial_period.pk
                config = _active_payroll_config_for_period(initial_period)
                if config:
                    self.initial["payroll_year_config"] = config.pk

    def clean(self):
        cleaned_data = super().clean()

        employee = cleaned_data.get("employee")
        pay_period = cleaned_data.get("pay_period")
        amount = cleaned_data.get("vacation_pay_amount")

        if not pay_period:
            return cleaned_data

        config = _active_payroll_config_for_period(pay_period)
        if not config:
            raise forms.ValidationError(
                f"No active payroll configuration exists for tax year {pay_period.tax_year}."
            )

        cleaned_data["payroll_year_config"] = config

        if employee and not _active_plan_for_period(employee, pay_period):
            raise forms.ValidationError(
                f"{employee.display_name} does not have an active compensation plan "
                f"covering this pay period."
            )

        if not employee or not amount:
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

        if not (cleaned_data.get("payment_note") or "").strip():
            cleaned_data["payment_note"] = (
                f"TownLIT Vacation Pay - {pay_period.end_date.strftime('%B %Y')}"
            )

        return cleaned_data
