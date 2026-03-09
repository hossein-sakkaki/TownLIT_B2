# apps/accounting/admin/forms.py

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from apps.accounting.models.account import  Account
from apps.accounting.models.accounting_period import AccountingPeriod
from apps.accounting.models.journal_entry import JournalEntry
from apps.accounting.models.transaction import Transaction
from apps.accounting.models.fund import Fund


ZERO = Decimal("0.00")


class JournalEntryAdminForm(forms.ModelForm):
    """
    Admin form for journal entries.
    """

    class Meta:
        model = JournalEntry
        fields = "__all__"

    def clean(self):
        """
        Validate journal entry fields.
        """

        cleaned_data = super().clean()

        status = cleaned_data.get("status")
        void_reason = cleaned_data.get("void_reason", "")

        if status == JournalEntry.STATUS_VOID and not void_reason.strip():
            raise ValidationError("Void reason is required when entry is voided.")

        return cleaned_data


class TransactionInlineFormSet(BaseInlineFormSet):
    """
    Validate transaction lines inside admin inline.
    """

    def clean(self):
        """
        Enforce balanced double-entry and valid lines.
        """

        super().clean()

        total_debit = ZERO
        total_credit = ZERO
        line_numbers = set()
        has_lines = False

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue

            if form.cleaned_data.get("DELETE", False):
                continue

            if not form.cleaned_data:
                continue

            account = form.cleaned_data.get("account")
            debit = form.cleaned_data.get("debit") or ZERO
            credit = form.cleaned_data.get("credit") or ZERO
            line_number = form.cleaned_data.get("line_number")

            if not account:
                continue

            has_lines = True

            if not account.is_active:
                raise ValidationError(
                    f"Account '{account}' is inactive and cannot be used."
                )

            if not account.allows_posting:
                raise ValidationError(
                    f"Account '{account}' is a group account and cannot receive postings."
                )

            if debit < ZERO or credit < ZERO:
                raise ValidationError("Debit and credit cannot be negative.")

            if debit == ZERO and credit == ZERO:
                raise ValidationError(
                    f"Line {line_number}: either debit or credit is required."
                )

            if debit > ZERO and credit > ZERO:
                raise ValidationError(
                    f"Line {line_number}: cannot have both debit and credit."
                )

            if line_number in line_numbers:
                raise ValidationError(f"Duplicate line number: {line_number}")
            line_numbers.add(line_number)

            total_debit += debit
            total_credit += credit

        if not has_lines:
            raise ValidationError("At least one transaction line is required.")

        if total_debit != total_credit:
            raise ValidationError(
                f"Entry is not balanced. Debit={total_debit}, Credit={total_credit}"
            )

        if total_debit <= ZERO:
            raise ValidationError("Total debit must be greater than zero.")


class TransactionAdminForm(forms.ModelForm):
    """
    Admin form for transaction line.
    """

    class Meta:
        model = Transaction
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        """
        Limit account choices to active postable accounts.
        """

        super().__init__(*args, **kwargs)
        self.fields["account"].queryset = Account.objects.filter(
            is_active=True,
            allows_posting=True,
        ).select_related("category").order_by("code")


# Choices for report formats and types -----------------------------------------------
REPORT_FORMAT_CHOICES = (
    ("csv", "CSV"),
    ("xlsx", "Excel (.xlsx)"),
    ("pdf", "PDF"),
    ("json", "JSON"),
)

ACCOUNTING_REPORT_CHOICES = (
    ("trial_balance", "Trial Balance"),
    ("founder_balance_summary", "Founder Balance Summary"),
    ("monthly_summary", "Monthly Summary"),
)

ACCOUNTING_OBJECT_REPORT_CHOICES = (
    ("general_ledger", "General Ledger"),
    ("fund_summary", "Fund Summary"),
    ("fund_ledger", "Fund Ledger"),
    ("budget_vs_actual", "Budget vs Actual"),
)


class AccountingReportHubForm(forms.Form):
    """
    Admin form for generating accounting reports.
    """

    report_type = forms.ChoiceField(choices=ACCOUNTING_REPORT_CHOICES)
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    file_format = forms.ChoiceField(choices=REPORT_FORMAT_CHOICES, initial="xlsx")


class AccountingObjectReportForm(forms.Form):
    """
    Admin form for object-based reports such as ledger/fund reports.
    """

    report_type = forms.ChoiceField(choices=ACCOUNTING_OBJECT_REPORT_CHOICES)
    account = forms.ModelChoiceField(
        queryset=Account.objects.filter(is_active=True).order_by("code"),
        required=False,
    )
    fund = forms.ModelChoiceField(
        queryset=Fund.objects.filter(is_active=True).order_by("code"),
        required=False,
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    file_format = forms.ChoiceField(choices=REPORT_FORMAT_CHOICES, initial="xlsx")

    def clean(self):
        """
        Validate report target selection.
        """

        cleaned_data = super().clean()
        report_type = cleaned_data.get("report_type")
        account = cleaned_data.get("account")
        fund = cleaned_data.get("fund")

        if report_type == "general_ledger" and not account:
            raise forms.ValidationError("Account is required for General Ledger.")

        if report_type in {"fund_summary", "fund_ledger", "budget_vs_actual"} and not fund:
            raise forms.ValidationError("Fund is required for fund reports.")

        return cleaned_data
    

# Form for fiscal year period generation --------------------------------------------------
class AccountingPeriodGenerationForm(forms.Form):
    """
    Admin form for generating a TownLIT fiscal year.
    """

    fy_start_year = forms.IntegerField(
        min_value=2000,
        max_value=2100,
        help_text="Example: 2025 creates FY2026 (June 2025 to May 2026).",
        label="Fiscal year start year",
    )

    default_status = forms.ChoiceField(
        choices=AccountingPeriod.STATUS_CHOICES,
        initial=AccountingPeriod.STATUS_OPEN,
        label="Default period status",
    )