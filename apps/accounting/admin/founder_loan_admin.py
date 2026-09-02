# apps/accounting/admin/founder_loan_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from apps.accounting.models import FounderLoan
from apps.accounting.services.templates.founder_records import (
    create_founder_loan_record,
    repay_founder_loan_record,
)

from .founder_loan_forms import FounderAdvanceAdminForm, FounderRepaymentAdminForm
from .site import accounting_admin_site


@admin.register(FounderLoan, site=accounting_admin_site)
class FounderLoanAdmin(admin.ModelAdmin):
    """
    Founder advance workflow and read-focused business ledger.

    Financial creation and repayment always go through the hardened founder
    record services. Raw FounderLoan creation is disabled.
    """

    change_list_template = "admin/accounting/founder_loan/change_list.html"
    change_form_template = "admin/accounting/founder_loan/change_form.html"

    list_display = (
        "lender_display_name",
        "loan_date",
        "principal_amount",
        "repaid_amount",
        "outstanding_amount_display",
        "status",
        "journal_entry_link",
    )
    list_filter = (
        "status",
        "currency",
        "loan_date",
    )
    search_fields = (
        "lender_display_name",
        "description",
        "internal_note",
        "journal_entry__entry_number",
        "journal_entry__reference",
    )
    ordering = ("-loan_date", "-id")
    list_select_related = ("lender", "journal_entry")
    list_per_page = 50

    readonly_fields = (
        "lender",
        "lender_display_name",
        "principal_amount",
        "repaid_amount",
        "outstanding_amount_display",
        "currency",
        "loan_date",
        "status",
        "description",
        "journal_entry_link",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Founder Advance",
            {
                "fields": (
                    "lender",
                    "lender_display_name",
                    "loan_date",
                    "principal_amount",
                    "repaid_amount",
                    "outstanding_amount_display",
                    "currency",
                    "status",
                ),
            },
        ),
        (
            "Accounting",
            {
                "fields": (
                    "description",
                    "journal_entry_link",
                ),
            },
        ),
        (
            "Internal Note",
            {
                "fields": ("internal_note",),
            },
        ),
        (
            "Audit",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "record-advance/",
                self.admin_site.admin_view(self.record_advance_view),
                name="accounting_founderloan_record_advance",
            ),
            path(
                "<int:object_id>/repay/",
                self.admin_site.admin_view(self.record_repayment_view),
                name="accounting_founderloan_repay",
            ),
        ]
        return custom_urls + urls

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Outstanding")
    def outstanding_amount_display(self, obj):
        return obj.outstanding_amount

    @admin.display(description="Journal Entry")
    def journal_entry_link(self, obj):
        if not obj or not obj.journal_entry_id:
            return "-"

        return format_html(
            '<a href="{}">{}</a>',
            reverse(
                "accounting_admin:accounting_journalentry_change",
                args=[obj.journal_entry_id],
            ),
            obj.journal_entry.entry_number,
        )

    def record_advance_view(self, request):
        if not request.user.has_perm("accounting.add_founderloan"):
            raise PermissionDenied

        if request.method == "POST":
            form = FounderAdvanceAdminForm(request.POST)

            if form.is_valid():
                try:
                    founder_loan = create_founder_loan_record(
                        lender=form.cleaned_data["lender"],
                        lender_display_name=form.cleaned_data["lender_display_name"],
                        entry_date=form.cleaned_data["entry_date"],
                        amount=form.cleaned_data["amount"],
                        expense_account_code=form.cleaned_data["expense_account"].code,
                        description=form.cleaned_data["description"],
                        reference=form.cleaned_data["reference"],
                        source_ref=form.cleaned_data["source_ref"],
                        created_by=request.user,
                        approved_by=request.user,
                    )

                    self.message_user(
                        request,
                        f"Founder advance recorded: {founder_loan.principal_amount}.",
                        level=messages.SUCCESS,
                    )

                    return redirect(
                        reverse(
                            "accounting_admin:accounting_founderloan_change",
                            args=[founder_loan.id],
                        )
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Founder advance could not be recorded: {exc}",
                        level=messages.ERROR,
                    )
        else:
            form = FounderAdvanceAdminForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Record Founder Advance",
            "form": form,
            "workflow_kind": "advance",
            "opts": self.model._meta,
        }

        return TemplateResponse(
            request,
            "admin/accounting/founder_loan/workflow_form.html",
            context,
        )

    def record_repayment_view(self, request, object_id):
        founder_loan = self.get_object(request, object_id)

        if founder_loan is None:
            raise PermissionDenied

        if not self.has_change_permission(request, founder_loan):
            raise PermissionDenied

        if request.method == "POST":
            form = FounderRepaymentAdminForm(
                request.POST,
                founder_loan=founder_loan,
            )

            if form.is_valid():
                try:
                    bank_account = form.cleaned_data["bank_account"]

                    entry = repay_founder_loan_record(
                        founder_loan=founder_loan,
                        entry_date=form.cleaned_data["entry_date"],
                        amount=form.cleaned_data["amount"],
                        repayment_ref=form.cleaned_data["repayment_ref"],
                        description=form.cleaned_data["description"],
                        reference=form.cleaned_data["reference"],
                        bank_account_code=bank_account.ledger_account.code,
                        created_by=request.user,
                        approved_by=request.user,
                    )

                    self.message_user(
                        request,
                        f"Founder repayment posted: {entry.entry_number}.",
                        level=messages.SUCCESS,
                    )

                    return redirect(
                        reverse(
                            "accounting_admin:accounting_founderloan_change",
                            args=[founder_loan.id],
                        )
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Founder repayment could not be posted: {exc}",
                        level=messages.ERROR,
                    )
        else:
            form = FounderRepaymentAdminForm(founder_loan=founder_loan)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Record Repayment — {founder_loan.lender_display_name}",
            "form": form,
            "founder_loan": founder_loan,
            "workflow_kind": "repayment",
            "opts": self.model._meta,
        }

        return TemplateResponse(
            request,
            "admin/accounting/founder_loan/workflow_form.html",
            context,
        )
