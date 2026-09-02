# apps/accounting/admin/founder_loan_forms.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from decimal import Decimal
from uuid import uuid4

from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import Account, BankAccount


class FounderAdvanceAdminForm(forms.Form):
    lender = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(),
        required=False,
        label="Founder / lender account",
        help_text="Optional. The display name below remains the accounting snapshot.",
    )
    lender_display_name = forms.CharField(
        max_length=255,
        label="Lender display name",
    )
    entry_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Date paid personally",
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Amount",
    )
    expense_account = forms.ModelChoiceField(
        queryset=Account.objects.none(),
        label="Expense account",
        help_text="Choose the expense TownLIT incurred and the founder paid personally.",
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Description",
    )
    reference = forms.CharField(
        max_length=255,
        required=False,
        label="Reference",
        help_text="Receipt, invoice, transfer, or other business reference.",
    )
    source_ref = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["lender"].queryset = get_user_model().objects.order_by("id")
        self.fields["expense_account"].queryset = Account.objects.filter(
            account_type=Account.TYPE_EXPENSE,
            is_active=True,
            allows_posting=True,
        ).order_by("code")

        if not self.is_bound:
            self.fields["source_ref"].initial = f"founder-advance-{uuid4().hex}"


class FounderRepaymentAdminForm(forms.Form):
    entry_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Paid on",
    )
    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
        label="Repayment amount",
    )
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.none(),
        label="Paid from bank account",
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Description",
    )
    reference = forms.CharField(
        max_length=255,
        required=False,
        label="Payment reference",
    )
    repayment_ref = forms.CharField(
        widget=forms.HiddenInput(),
        required=True,
    )

    def __init__(self, *args, founder_loan=None, **kwargs):
        self.founder_loan = founder_loan
        super().__init__(*args, **kwargs)

        self.fields["bank_account"].queryset = (
            BankAccount.objects.select_related("ledger_account", "institution")
            .filter(
                status=BankAccount.STATUS_ACTIVE,
                is_active=True,
                ledger_account__is_active=True,
                ledger_account__allows_posting=True,
            )
            .order_by("-is_primary", "code")
        )

        if not self.is_bound:
            self.fields["repayment_ref"].initial = f"founder-repayment-{uuid4().hex}"

            if founder_loan is not None:
                self.fields["amount"].initial = founder_loan.outstanding_amount
                self.fields["description"].initial = (
                    f"Founder loan repayment to {founder_loan.lender_display_name}"
                )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if self.founder_loan is not None and amount > self.founder_loan.outstanding_amount:
            raise forms.ValidationError(
                f"Repayment cannot exceed the outstanding balance "
                f"({self.founder_loan.outstanding_amount})."
            )

        return amount
