# apps/accounting/admin/payroll_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from decimal import Decimal
from django.http import HttpResponse, JsonResponse

from apps.accounting.models import (
    PayrollYearConfig,
    PayrollEmployee,
    PayrollCompensationPlan,
    PaySchedule,
    PayPeriod,
    PayRun,
    PayStub,
    PayrollRemittance,
    PayrollLeavePolicy,
    PayrollLeaveBalance,
    PayrollLeaveEntry,
    PayrollWorkSummary,
)
from apps.accounting.services.payroll import (
    PayrollRunService,
    PayrollPostingService,
    PayrollRemittanceService,
)
from .payroll_forms import (
    CreatePayRunAdminForm,
    RecordSalaryPaymentAdminForm,
    RecordPayrollRemittancePaymentAdminForm,
)

from .site import accounting_admin_site
from apps.accounting.services.payroll.comparison_service import PayrollComparisonService
from apps.accounting.reports.http import build_file_response
from apps.accounting.services.payroll.paystub_pdf_service import PayStubPDFService
from apps.accounting.services.payroll.payroll_register_service import PayrollRegisterService
from apps.accounting.services.email.payroll_email_service import PayrollEmailService
from .payroll_forms import CreateVacationPayRunAdminForm
from apps.accounting.services.payroll.vacation_balance_service import VacationPayBalanceService
from apps.accounting.services.payroll.payroll_type_service import is_vacation_pay_run
from apps.accounting.services.payroll.vacation_pay_pdf_service import VacationPayPDFService
from apps.accounting.services.payroll.payroll_type_service import is_vacation_pay_stub


# ----------------------------------------------------------------------------
# Pay Stub Inline Admin 
# ----------------------------------------------------------------------------
class PayStubInline(admin.TabularInline):
    """
    Inline pay stubs under a pay run.
    """

    model = PayStub
    extra = 1
    can_delete = False

    readonly_fields = (
        "employee",
        "gross_salary",
        "vacation_pay_earned",
        "vacation_pay_paid",
        "sick_pay_paid",
        "taxable_benefits",
        "pensionable_earnings",
        "insurable_earnings",
        "taxable_earnings",
        "employee_cpp",
        "employee_cpp2",
        "employee_ei",
        "federal_income_tax",
        "provincial_income_tax",
        "total_employee_deductions",
        "employer_cpp",
        "employer_cpp2",
        "employer_ei",
        "total_employer_contributions",
        "net_pay",
        "actual_paid",
        "net_salary_payable",
        "total_remittance_due",
        "payment_note",
        "pay_stub_pdf_link",
    )

    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description="PDF")
    def pay_stub_pdf_link(self, obj):
        """
        Link to pay stub PDF.
        """

        if not obj or not obj.id:
            return "-"

        return format_html(
            '<a class="button" href="{}">PDF</a>',
            reverse(
                "accounting_admin:accounting_paystub_pdf",
                args=[obj.id],
            ),
        )

# ----------------------------------------------------------------------------
# PayrollYearConfig Admin
# ----------------------------------------------------------------------------
@admin.register(PayrollYearConfig, site=accounting_admin_site)
class PayrollYearConfigAdmin(admin.ModelAdmin):
    """
    Admin for yearly payroll rules.
    """

    list_display = (
        "year",
        "province",
        "currency",
        "cpp_enabled",
        "ei_enabled",
        "is_active",
        "updated_at",
    )
    list_filter = ("year", "province", "cpp_enabled", "ei_enabled", "is_active")
    search_fields = ("year", "province", "note")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Basic",
            {
                "fields": (
                    "year",
                    "country",
                    "province",
                    "currency",
                    "is_active",
                    "note",
                )
            },
        ),
        (
            "CPP",
            {
                "fields": (
                    "cpp_enabled",
                    "cpp_rate_employee",
                    "cpp_rate_employer",
                    "cpp_basic_exemption_annual",
                    "cpp_max_pensionable_earnings",
                )
            },
        ),
        (
            "CPP2",
            {
                "fields": (
                    "cpp2_enabled",
                    "cpp2_rate_employee",
                    "cpp2_rate_employer",
                    "cpp2_max_additional_earnings",
                )
            },
        ),
        (
            "EI",
            {
                "fields": (
                    "ei_enabled",
                    "ei_rate_employee",
                    "ei_rate_employer_multiplier",
                    "ei_max_insurable_earnings",
                )
            },
        ),
        (
            "Income Tax",
            {
                "fields": (
                    "federal_tax_config",
                    "provincial_tax_config",
                    "default_federal_td1_amount",
                    "default_provincial_td1_amount",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


# ----------------------------------------------------------------------------
# PayrollEmployee Admin
# ----------------------------------------------------------------------------
class PayrollCompensationPlanInline(admin.StackedInline):
    """Keep the active compensation setup on the employee page."""

    model = PayrollCompensationPlan
    extra = 0
    can_delete = False
    show_change_link = True
    max_num = 6
    fields = (
        "status",
        "pay_type",
        "monthly_salary",
        "hourly_rate",
        "default_regular_hours_per_period",
        "vacation_pay_enabled",
        "vacation_pay_rate",
        "vacation_pay_mode",
        "sick_leave_enabled",
        "effective_from",
        "effective_to",
        "board_resolution_date",
        "approval_reference",
        "note",
    )


@admin.register(PayrollEmployee, site=accounting_admin_site)
class PayrollEmployeeAdmin(admin.ModelAdmin):
    """Payroll employee setup with compensation and quick workflow access."""

    list_display = (
        "display_name",
        "employment_type",
        "province_of_employment",
        "pay_setup_display",
        "employment_start_date",
        "email",
        "is_active",
        "quick_payroll_action",
    )
    list_filter = (
        "employment_type",
        "province_of_employment",
        "is_active",
        "cpp_exempt",
        "ei_exempt",
        "income_tax_exempt",
    )
    search_fields = (
        "display_name",
        "legal_first_name",
        "legal_last_name",
        "email",
        "phone",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = (PayrollCompensationPlanInline,)
    change_form_template = "admin/accounting/payroll/employee_change_form.html"

    fieldsets = (
        (
            "Employee Identity",
            {
                "fields": (
                    "user",
                    "legal_first_name",
                    "legal_last_name",
                    "display_name",
                    "employment_type",
                    "province_of_employment",
                    "employment_start_date",
                    "employment_end_date",
                )
            },
        ),
        (
            "Tax & Payroll Settings",
            {
                "fields": (
                    "cpp_exempt",
                    "ei_exempt",
                    "income_tax_exempt",
                    "federal_td1_amount",
                    "provincial_td1_amount",
                    "is_director",
                    "is_related_to_employer",
                ),
                "description": (
                    "Checked exemption boxes mean the deduction is NOT calculated. "
                    "Compensation is managed directly below on this same employee page."
                ),
            },
        ),
        (
            "Contact Information",
            {
                "fields": (
                    "email",
                    "phone",
                    "address_line1",
                    "address_line2",
                    "city",
                    "province",
                    "postal_code",
                    "country",
                )
            },
        ),
        (
            "Status and Notes",
            {"fields": ("is_active", "internal_note")},
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("compensation_plans")

    def _active_plan(self, obj):
        plans = [
            plan
            for plan in obj.compensation_plans.all()
            if plan.status == PayrollCompensationPlan.STATUS_ACTIVE
        ]
        if not plans:
            return None
        return sorted(plans, key=lambda item: (item.effective_from, item.id), reverse=True)[0]

    @admin.display(description="Pay setup")
    def pay_setup_display(self, obj):
        plan = self._active_plan(obj)
        if not plan:
            return format_html('<strong style="color:#b42318">Setup required</strong>')

        if plan.pay_type == PayrollCompensationPlan.PAY_TYPE_HOURLY:
            return f"Hourly — ${plan.hourly_rate}/hr"

        return f"Monthly — ${plan.monthly_salary}/month"

    @admin.display(description="Payroll")
    def quick_payroll_action(self, obj):
        if not obj.pk or not obj.is_active or not self._active_plan(obj):
            return "-"

        url = reverse("accounting_admin:accounting-create-pay-run")
        return format_html(
            '<a class="button" href="{}?employee={}">Create Payroll</a>',
            url,
            obj.id,
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        employee = self.get_object(request, object_id)

        if employee:
            extra_context["payroll_active_plan"] = self._active_plan(employee)
            extra_context["payroll_create_url"] = (
                f'{reverse("accounting_admin:accounting-create-pay-run")}?employee={employee.id}'
            )
            extra_context["payroll_recent_stubs"] = (
                employee.pay_stubs.select_related("pay_run", "pay_run__pay_period")
                .order_by("-pay_run__run_date", "-id")[:6]
            )

        return super().change_view(
            request,
            object_id,
            form_url,
            extra_context=extra_context,
        )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, PayrollCompensationPlan) and not instance.created_by_id:
                instance.created_by = request.user
            instance.save()

        for deleted in formset.deleted_objects:
            deleted.delete()

        formset.save_m2m()


# ----------------------------------------------------------------------------
# PayrollCompensationPlan Admin
# ----------------------------------------------------------------------------
@admin.register(PayrollCompensationPlan, site=accounting_admin_site)
class PayrollCompensationPlanAdmin(admin.ModelAdmin):
    """
    Admin for approved compensation plans.
    """

    list_display = (
        "employee",
        "pay_type",
        "monthly_salary",
        "hourly_rate",
        "default_regular_hours_per_period",
        "effective_from",
        "effective_to",
        "vacation_pay_enabled",
        "vacation_pay_rate",
        "vacation_pay_mode",
        "status",
    )

    list_filter = (
        "pay_type",
        "status",
        "vacation_pay_enabled",
        "vacation_pay_mode",
        "sick_leave_enabled",
    )

    search_fields = (
        "employee__display_name",
        "employee__legal_first_name",
        "employee__legal_last_name",
        "approval_reference",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Employee and Pay Type",
            {
                "fields": (
                    "employee",
                    "pay_type",
                    "status",
                )
            },
        ),
        (
            "Monthly Salary",
            {
                "fields": (
                    "monthly_salary",
                )
            },
        ),
        (
            "Hourly Pay",
            {
                "fields": (
                    "hourly_rate",
                    "default_regular_hours_per_period",
                )
            },
        ),
        (
            "Overtime Rules",
            {
                "fields": (
                    "daily_overtime_after_hours",
                    "daily_double_time_after_hours",
                    "weekly_overtime_after_hours",
                    "overtime_rate_multiplier",
                    "double_time_rate_multiplier",
                ),
                "description": (
                    "Legal overtime rule defaults. Only superusers should modify these values."
                ),
            },
        ),
        (
            "Vacation and Sick Pay",
            {
                "fields": (
                    "vacation_pay_enabled",
                    "vacation_pay_rate",
                    "vacation_pay_mode",
                    "sick_leave_enabled",
                )
            },
        ),
        (
            "Approval and Effective Dates",
            {
                "fields": (
                    "effective_from",
                    "effective_to",
                    "board_resolution_date",
                    "approval_reference",
                    "note",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    class Media:
        js = (
            "accounting/admin/payroll_compensation_plan.js",
        )

    def get_readonly_fields(self, request, obj=None):
        """
        Lock legal overtime defaults for non-superusers.
        """

        readonly = list(super().get_readonly_fields(request, obj))

        if not request.user.is_superuser:
            readonly.extend(
                [
                    "daily_overtime_after_hours",
                    "daily_double_time_after_hours",
                    "weekly_overtime_after_hours",
                    "overtime_rate_multiplier",
                    "double_time_rate_multiplier",
                ]
            )

        return readonly

    def get_changeform_initial_data(self, request):
        """
        Set safe BC overtime defaults on new plans.
        """

        initial = super().get_changeform_initial_data(request)

        initial.setdefault("daily_overtime_after_hours", "8.00")
        initial.setdefault("daily_double_time_after_hours", "12.00")
        initial.setdefault("weekly_overtime_after_hours", "40.00")
        initial.setdefault("overtime_rate_multiplier", "1.500")
        initial.setdefault("double_time_rate_multiplier", "2.000")

        return initial

    def save_model(self, request, obj, form, change):
        """
        Prevent accidental non-superuser overtime rule changes.
        """

        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user

        if change and not request.user.is_superuser:
            original = PayrollCompensationPlan.objects.get(pk=obj.pk)

            obj.daily_overtime_after_hours = original.daily_overtime_after_hours
            obj.daily_double_time_after_hours = original.daily_double_time_after_hours
            obj.weekly_overtime_after_hours = original.weekly_overtime_after_hours
            obj.overtime_rate_multiplier = original.overtime_rate_multiplier
            obj.double_time_rate_multiplier = original.double_time_rate_multiplier

        super().save_model(request, obj, form, change)


# ----------------------------------------------------------------------------
# PaySchedule Admin
# ----------------------------------------------------------------------------
@admin.register(PaySchedule, site=accounting_admin_site)
class PayScheduleAdmin(admin.ModelAdmin):
    """
    Admin for pay schedules.
    """

    list_display = ("code", "name", "frequency", "is_active")
    list_filter = ("frequency", "is_active")
    search_fields = ("code", "name", "description")
    readonly_fields = ("created_at", "updated_at")


# ----------------------------------------------------------------------------
# PayPeriod Admin
# ----------------------------------------------------------------------------
@admin.register(PayPeriod, site=accounting_admin_site)
class PayPeriodAdmin(admin.ModelAdmin):
    """
    Admin for pay periods.
    """

    list_display = (
        "code",
        "schedule",
        "tax_year",
        "start_date",
        "end_date",
        "pay_date",
        "status",
    )
    list_filter = ("schedule", "tax_year", "status")
    search_fields = ("code", "note")
    readonly_fields = ("created_at", "updated_at")


# ----------------------------------------------------------------------------
# PayRun Admin
# ----------------------------------------------------------------------------
@admin.register(PayRun, site=accounting_admin_site)
class PayRunAdmin(admin.ModelAdmin):
    """Workflow-first admin for calculated payroll runs."""

    list_display = (
        "run_number",
        "pay_period",
        "run_date",
        "status",
        "total_gross_pay",
        "total_net_pay",
        "total_actual_paid",
        "total_salary_payable",
        "total_remittance_due",
        "admin_actions",
    )
    list_filter = ("status", "run_date", "pay_period__tax_year")
    search_fields = ("run_number", "description", "internal_note")
    readonly_fields = (
        "run_number",
        "status",
        "total_gross_pay",
        "total_employee_deductions",
        "total_employer_contributions",
        "total_net_pay",
        "total_actual_paid",
        "total_salary_payable",
        "total_remittance_due",
        "journal_entry",
        "approved_by",
        "approved_at",
        "posted_at",
        "created_by",
        "created_at",
        "updated_at",
        "admin_actions",
    )
    inlines = (PayStubInline,)
    actions = ("approve_selected_pay_runs", "create_remittance_for_selected")
    change_list_template = "admin/accounting/payrun/change_list.html"
    change_form_template = "admin/accounting/payroll/pay_run_change_form.html"

    fieldsets = (
        (
            "Payroll Run",
            {
                "fields": (
                    "run_number",
                    "status",
                    "pay_period",
                    "payroll_year_config",
                    "run_date",
                    "description",
                    "internal_note",
                )
            },
        ),
        (
            "Totals",
            {
                "fields": (
                    "total_gross_pay",
                    "total_employee_deductions",
                    "total_employer_contributions",
                    "total_net_pay",
                    "total_actual_paid",
                    "total_salary_payable",
                    "total_remittance_due",
                )
            },
        ),
        (
            "Ledger & Approval",
            {
                "fields": (
                    "journal_entry",
                    "approved_by",
                    "approved_at",
                    "posted_at",
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly.extend(("pay_period", "payroll_year_config", "run_date"))
        return tuple(dict.fromkeys(readonly))

    def _salary_payment_completed(self, pay_run):
        return not pay_run.pay_stubs.filter(net_salary_payable__gt=0).exists()

    def _remittance(self, pay_run):
        try:
            return pay_run.remittance
        except PayrollRemittance.DoesNotExist:
            return None

    def _workflow_payload(self, pay_run):
        remittance = self._remittance(pay_run)
        has_salary_due = not self._salary_payment_completed(pay_run)

        next_action = None
        if pay_run.status == PayRun.STATUS_CALCULATED:
            next_action = {
                "label": "Approve Payroll",
                "url": reverse("accounting_admin:accounting_payrun_approve", args=[pay_run.id]),
                "method": "post",
                "tone": "warning",
            }
        elif pay_run.status == PayRun.STATUS_APPROVED:
            next_action = {
                "label": "Post to Ledger",
                "url": reverse("accounting_admin:accounting_payrun_post", args=[pay_run.id]),
                "method": "post",
                "tone": "primary",
            }
        elif pay_run.status in {PayRun.STATUS_POSTED, PayRun.STATUS_PAID} and has_salary_due:
            next_action = {
                "label": "Record Salary Payment",
                "url": reverse(
                    "accounting_admin:accounting_payrun_record_salary_payment",
                    args=[pay_run.id],
                ),
                "method": "get",
                "tone": "primary",
            }
        elif pay_run.status in {PayRun.STATUS_POSTED, PayRun.STATUS_PAID}:
            if pay_run.total_remittance_due > 0 and remittance is None:
                next_action = {
                    "label": "Create CRA Remittance",
                    "url": reverse(
                        "accounting_admin:accounting_payrun_create_remittance",
                        args=[pay_run.id],
                    ),
                    "method": "post",
                    "tone": "warning",
                }
            elif remittance and remittance.status in {
                PayrollRemittance.STATUS_DRAFT,
                PayrollRemittance.STATUS_READY,
            } and not remittance.journal_entry_id:
                next_action = {
                    "label": "Record CRA Payment",
                    "url": reverse(
                        "accounting_admin:accounting_payrollremittance_record_payment",
                        args=[remittance.id],
                    ),
                    "method": "get",
                    "tone": "primary",
                }

        status_order = [
            PayRun.STATUS_CALCULATED,
            PayRun.STATUS_APPROVED,
            PayRun.STATUS_POSTED,
            PayRun.STATUS_PAID,
        ]
        current_index = status_order.index(pay_run.status) if pay_run.status in status_order else -1
        steps = []
        for index, status in enumerate(status_order):
            steps.append(
                {
                    "label": dict(PayRun.STATUS_CHOICES)[status],
                    "done": current_index >= index,
                    "current": current_index == index,
                }
            )

        stubs = []
        for stub in pay_run.pay_stubs.select_related("employee").order_by("employee__display_name"):
            stubs.append(
                {
                    "employee": stub.employee,
                    "gross": stub.gross_salary,
                    "net": stub.net_pay,
                    "paid": stub.actual_paid,
                    "due": stub.net_salary_payable,
                    "pdf_url": reverse(
                        "accounting_admin:accounting_paystub_pdf",
                        args=[stub.id],
                    ),
                    "change_url": reverse(
                        "accounting_admin:accounting_paystub_change",
                        args=[stub.id],
                    ),
                }
            )

        return {
            "steps": steps,
            "next_action": next_action,
            "has_salary_due": has_salary_due,
            "remittance": remittance,
            "remittance_pay_url": (
                reverse(
                    "accounting_admin:accounting_payrollremittance_record_payment",
                    args=[remittance.id],
                )
                if remittance
                and remittance.status in {
                    PayrollRemittance.STATUS_DRAFT,
                    PayrollRemittance.STATUS_READY,
                }
                and not remittance.journal_entry_id
                else ""
            ),
            "journal_url": (
                reverse(
                    "accounting_admin:accounting_journalentry_change",
                    args=[pay_run.journal_entry_id],
                )
                if pay_run.journal_entry_id
                else ""
            ),
            "register_xlsx_url": reverse(
                "accounting_admin:accounting_payrun_register",
                args=[pay_run.id, "xlsx"],
            ),
            "register_pdf_url": reverse(
                "accounting_admin:accounting_payrun_register",
                args=[pay_run.id, "pdf"],
            ),
            "stubs": stubs,
        }

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        pay_run = self.get_object(request, object_id)
        if pay_run:
            extra_context["payroll_workflow"] = self._workflow_payload(pay_run)
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    @admin.action(description="Approve selected calculated pay runs")
    def approve_selected_pay_runs(self, request, queryset):
        service = PayrollRunService()
        email_service = PayrollEmailService()
        count = 0

        for pay_run in queryset:
            try:
                service.approve_pay_run(pay_run=pay_run, approved_by=request.user)
                for stub in pay_run.pay_stubs.select_related("employee", "employee__user"):
                    email_service.send_pay_stub_approved_email(pay_stub=stub)
                count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{pay_run.run_number}: {exc}",
                    level=messages.ERROR,
                )

        if count:
            self.message_user(request, f"{count} pay run(s) approved.", level=messages.SUCCESS)

    @admin.action(description="Create remittance for selected posted pay runs")
    def create_remittance_for_selected(self, request, queryset):
        service = PayrollRunService()
        count = 0

        for pay_run in queryset:
            try:
                service.create_remittance_for_pay_run(
                    pay_run=pay_run,
                    due_date=pay_run.pay_period.pay_date,
                )
                count += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{pay_run.run_number}: {exc}",
                    level=messages.ERROR,
                )

        if count:
            self.message_user(
                request,
                f"{count} remittance record(s) created.",
                level=messages.SUCCESS,
            )

    @admin.display(description="Next step")
    def admin_actions(self, obj):
        if not obj or not obj.id:
            return "-"

        workflow = self._workflow_payload(obj)
        action = workflow["next_action"]

        if not action:
            return format_html(
                '<a class="button" href="{}">Open</a>',
                reverse("accounting_admin:accounting_payrun_change", args=[obj.id]),
            )

        return format_html(
            '<a class="button" href="{}">{}</a>',
            action["url"],
            action["label"],
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "create-pay-run/",
                self.admin_site.admin_view(self.create_pay_run_view),
                name="accounting-create-pay-run",
            ),
            path(
                "<int:object_id>/approve/",
                self.admin_site.admin_view(self.approve_pay_run_view),
                name="accounting_payrun_approve",
            ),
            path(
                "<int:object_id>/post/",
                self.admin_site.admin_view(self.post_pay_run_view),
                name="accounting_payrun_post",
            ),
            path(
                "<int:object_id>/record-salary-payment/",
                self.admin_site.admin_view(self.record_salary_payment_view),
                name="accounting_payrun_record_salary_payment",
            ),
            path(
                "<int:object_id>/create-remittance/",
                self.admin_site.admin_view(self.create_remittance_view),
                name="accounting_payrun_create_remittance",
            ),
            path(
                "<int:object_id>/register/<str:file_format>/",
                self.admin_site.admin_view(self.payroll_register_view),
                name="accounting_payrun_register",
            ),
            path(
                "create-vacation-pay-run/",
                self.admin_site.admin_view(self.create_vacation_pay_run_view),
                name="accounting-create-vacation-pay-run",
            ),
            path(
                "vacation-balance/",
                self.admin_site.admin_view(self.vacation_balance_view),
                name="accounting_vacation_balance",
            ),
        ]
        return custom_urls + urls

    def payroll_register_view(self, request, object_id, file_format):
        pay_run = self.get_object(request, object_id)
        try:
            content, filename, content_type_key = PayrollRegisterService().export(
                pay_run=pay_run,
                file_format=file_format,
            )
            return build_file_response(
                content=content,
                filename=filename,
                file_format=content_type_key,
            )
        except Exception as exc:
            self.message_user(
                request,
                f"Payroll register export failed: {exc}",
                level=messages.ERROR,
            )
            return redirect(
                reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id])
            )

    def _confirmation(self, request, pay_run, *, title, message, button_label):
        return TemplateResponse(
            request,
            "admin/accounting/payroll/action_confirm.html",
            {
                **self.admin_site.each_context(request),
                "title": title,
                "pay_run": pay_run,
                "message": message,
                "button_label": button_label,
                "opts": self.model._meta,
            },
        )

    def approve_pay_run_view(self, request, object_id):
        pay_run = self.get_object(request, object_id)

        if request.method != "POST":
            return self._confirmation(
                request,
                pay_run,
                title=f"Approve Payroll - {pay_run.run_number}",
                message="Approve the calculated payroll and send approved pay stub email notifications.",
                button_label="Approve Payroll",
            )

        try:
            PayrollRunService().approve_pay_run(
                pay_run=pay_run,
                approved_by=request.user,
            )
            email_service = PayrollEmailService()
            sent_count = 0
            for stub in pay_run.pay_stubs.select_related("employee", "employee__user"):
                if email_service.send_pay_stub_approved_email(pay_stub=stub):
                    sent_count += 1
            self.message_user(
                request,
                f"Pay run {pay_run.run_number} approved. Pay stub email(s) sent: {sent_count}.",
                level=messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(request, f"Approval failed: {exc}", level=messages.ERROR)

        return redirect(reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id]))

    def post_pay_run_view(self, request, object_id):
        pay_run = self.get_object(request, object_id)

        if request.method != "POST":
            return self._confirmation(
                request,
                pay_run,
                title=f"Post Payroll - {pay_run.run_number}",
                message="Post this approved payroll accrual to the protected accounting ledger.",
                button_label="Post to Ledger",
            )

        try:
            journal_entry = PayrollPostingService().post_pay_run(
                pay_run=pay_run,
                created_by=request.user,
                approved_by=request.user,
            )
            self.message_user(
                request,
                f"Payroll posted to ledger: {journal_entry.entry_number}",
                level=messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(request, f"Posting failed: {exc}", level=messages.ERROR)

        return redirect(reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id]))

    def record_salary_payment_view(self, request, object_id):
        pay_run = self.get_object(request, object_id)
        payable_stubs = list(
            pay_run.pay_stubs.select_related("employee")
            .filter(net_salary_payable__gt=0)
            .order_by("id")
        )
        total_remaining_payable = sum(
            (stub.net_salary_payable or Decimal("0.00")) for stub in payable_stubs
        )

        if request.method == "POST":
            form = RecordSalaryPaymentAdminForm(request.POST)
            if form.is_valid():
                try:
                    paid_on = form.cleaned_data["paid_on"]
                    selected_bank = form.cleaned_data["bank_account_code"]
                    bank_account_code = selected_bank.ledger_account.code
                    payment_reference = form.cleaned_data["payment_reference"]
                    payment_method = form.cleaned_data["payment_method"]
                    amount_to_pay = form.cleaned_data["payment_amount"]

                    if is_vacation_pay_run(pay_run=pay_run) and amount_to_pay != total_remaining_payable:
                        raise ValueError(
                            f"Vacation pay payments must be paid in full. Required amount: {total_remaining_payable}."
                        )

                    if amount_to_pay > total_remaining_payable:
                        raise ValueError(
                            f"Payment amount cannot exceed remaining payable amount ({total_remaining_payable})."
                        )

                    remaining_to_allocate = amount_to_pay
                    created_count = 0
                    paid_stub_ids = []
                    posting_service = PayrollPostingService()

                    for stub in payable_stubs:
                        if remaining_to_allocate <= Decimal("0.00"):
                            break

                        stub_remaining = stub.net_salary_payable or Decimal("0.00")
                        payment_for_stub = min(stub_remaining, remaining_to_allocate)
                        payment = posting_service.post_salary_payment(
                            pay_stub=stub,
                            paid_on=paid_on,
                            bank_account_code=bank_account_code,
                            payment_reference=payment_reference or stub.payment_note,
                            payment_method=payment_method,
                            payment_amount=payment_for_stub,
                            created_by=request.user,
                            approved_by=request.user,
                        )
                        created_count += 1
                        paid_stub_ids.append(stub.id)
                        remaining_to_allocate -= payment.amount

                    if created_count == 0:
                        raise ValueError("No payable salary balance was found.")

                    email_service = PayrollEmailService()
                    email_count = 0
                    paid_stubs = PayStub.objects.filter(id__in=paid_stub_ids).select_related(
                        "employee", "employee__user"
                    )
                    for stub in paid_stubs:
                        if email_service.send_salary_payment_confirmation_email(pay_stub=stub):
                            email_count += 1

                    self.message_user(
                        request,
                        (
                            f"{created_count} salary payment journal entry/entries created. "
                            f"Payment confirmation email(s) sent: {email_count}."
                        ),
                        level=messages.SUCCESS,
                    )
                    return redirect(
                        reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id])
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Salary payment failed: {exc}",
                        level=messages.ERROR,
                    )
        else:
            form = RecordSalaryPaymentAdminForm(
                initial={
                    "paid_on": pay_run.pay_period.pay_date,
                    "payment_amount": total_remaining_payable,
                    "payment_reference": (
                        f"TownLIT Payroll - {pay_run.pay_period.end_date.strftime('%B %Y')}"
                    ),
                }
            )

        return TemplateResponse(
            request,
            "admin/accounting/payroll/record_salary_payment.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Record Salary Payment - {pay_run.run_number}",
                "form": form,
                "pay_run": pay_run,
                "total_remaining_payable": total_remaining_payable,
                "payable_stubs": payable_stubs,
                "opts": self.model._meta,
            },
        )

    def create_remittance_view(self, request, object_id):
        pay_run = self.get_object(request, object_id)

        if request.method != "POST":
            return self._confirmation(
                request,
                pay_run,
                title=f"Create CRA Remittance - {pay_run.run_number}",
                message=(
                    f"Create the CRA remittance record for this payroll. "
                    f"Current remittance due: {pay_run.total_remittance_due}."
                ),
                button_label="Create CRA Remittance",
            )

        try:
            remittance = PayrollRunService().create_remittance_for_pay_run(pay_run=pay_run)
            self.message_user(
                request,
                f"Payroll remittance ready: {remittance.total_due}",
                level=messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(
                request,
                f"Remittance creation failed: {exc}",
                level=messages.ERROR,
            )

        return redirect(reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id]))

    def create_pay_run_view(self, request):
        if request.method == "POST":
            form = CreatePayRunAdminForm(request.POST)
            if form.is_valid():
                employee = form.cleaned_data["employee"]
                overrides = {}
                if form.cleaned_data.get("use_manual_overrides"):
                    overrides = {
                        "employee_cpp": form.cleaned_data.get("employee_cpp"),
                        "employer_cpp": form.cleaned_data.get("employer_cpp"),
                        "employee_cpp2": form.cleaned_data.get("employee_cpp2"),
                        "employer_cpp2": form.cleaned_data.get("employer_cpp2"),
                        "employee_ei": form.cleaned_data.get("employee_ei"),
                        "employer_ei": form.cleaned_data.get("employer_ei"),
                        "federal_income_tax": form.cleaned_data.get("federal_income_tax"),
                        "provincial_income_tax": form.cleaned_data.get("provincial_income_tax"),
                        "override_source": form.cleaned_data.get("override_source", ""),
                        "override_note": form.cleaned_data.get("override_note", ""),
                    }

                try:
                    pay_run = PayrollRunService().create_monthly_pay_run(
                        pay_period=form.cleaned_data["pay_period"],
                        payroll_year_config=form.cleaned_data["payroll_year_config"],
                        employees=[employee],
                        actual_paid_by_employee_id={employee.id: Decimal("0.00")},
                        payment_note_by_employee_id={
                            employee.id: form.cleaned_data.get("payment_note", ""),
                        },
                        override_by_employee_id={employee.id: overrides},
                        created_by=request.user,
                        hourly_input_by_employee_id={
                            employee.id: {
                                "regular_hours": form.cleaned_data.get("regular_hours") or 0,
                                "daily_overtime_hours": form.cleaned_data.get("daily_overtime_hours") or 0,
                                "weekly_overtime_hours": form.cleaned_data.get("weekly_overtime_hours") or 0,
                                "double_time_hours": form.cleaned_data.get("double_time_hours") or 0,
                            }
                        },
                    )
                    self.message_user(
                        request,
                        f"Pay run {pay_run.run_number} created successfully.",
                        level=messages.SUCCESS,
                    )
                    return redirect(
                        reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id])
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Payroll creation failed: {exc}",
                        level=messages.ERROR,
                    )
        else:
            initial = {}
            if request.GET.get("employee"):
                initial["employee"] = request.GET.get("employee")
            if request.GET.get("pay_period"):
                initial["pay_period"] = request.GET.get("pay_period")
            form = CreatePayRunAdminForm(initial=initial)

        return TemplateResponse(
            request,
            "admin/accounting/payroll/create_pay_run.html",
            {
                **self.admin_site.each_context(request),
                "title": "Create Payroll Run",
                "form": form,
                "opts": self.model._meta,
            },
        )

    def create_vacation_pay_run_view(self, request):
        if request.method == "POST":
            form = CreateVacationPayRunAdminForm(request.POST)
            if form.is_valid():
                employee = form.cleaned_data["employee"]
                overrides = {}
                if form.cleaned_data.get("use_manual_overrides"):
                    overrides = {
                        "employee_cpp": form.cleaned_data.get("employee_cpp"),
                        "employer_cpp": form.cleaned_data.get("employer_cpp"),
                        "employee_cpp2": form.cleaned_data.get("employee_cpp2"),
                        "employer_cpp2": form.cleaned_data.get("employer_cpp2"),
                        "employee_ei": form.cleaned_data.get("employee_ei"),
                        "employer_ei": form.cleaned_data.get("employer_ei"),
                        "federal_income_tax": form.cleaned_data.get("federal_income_tax"),
                        "provincial_income_tax": form.cleaned_data.get("provincial_income_tax"),
                        "override_source": form.cleaned_data.get("override_source", ""),
                        "override_note": form.cleaned_data.get("override_note", ""),
                    }

                try:
                    pay_run = PayrollRunService().create_vacation_pay_run(
                        pay_period=form.cleaned_data["pay_period"],
                        payroll_year_config=form.cleaned_data["payroll_year_config"],
                        employee=employee,
                        vacation_pay_amount=form.cleaned_data["vacation_pay_amount"],
                        payment_note=form.cleaned_data.get("payment_note", ""),
                        override_values=overrides,
                        created_by=request.user,
                    )
                    self.message_user(
                        request,
                        f"Vacation pay run {pay_run.run_number} created successfully.",
                        level=messages.SUCCESS,
                    )
                    return redirect(
                        reverse("accounting_admin:accounting_payrun_change", args=[pay_run.id])
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"Vacation pay run creation failed: {exc}",
                        level=messages.ERROR,
                    )
        else:
            initial = {}
            if request.GET.get("employee"):
                initial["employee"] = request.GET.get("employee")
            if request.GET.get("pay_period"):
                initial["pay_period"] = request.GET.get("pay_period")
            form = CreateVacationPayRunAdminForm(initial=initial)

        return TemplateResponse(
            request,
            "admin/accounting/payroll/create_vacation_pay_run.html",
            {
                **self.admin_site.each_context(request),
                "title": "Create Vacation Pay Run",
                "form": form,
                "opts": self.model._meta,
            },
        )

    def vacation_balance_view(self, request):
        employee_id = request.GET.get("employee_id")
        pay_period_id = request.GET.get("pay_period_id")
        if not employee_id or not pay_period_id:
            return JsonResponse(
                {"ok": False, "message": "Employee and pay period are required."},
                status=400,
            )

        try:
            employee = PayrollEmployee.objects.get(id=employee_id, is_active=True)
            pay_period = PayPeriod.objects.get(id=pay_period_id)
            balance_service = VacationPayBalanceService()
            balance = balance_service.get_balance(
                employee=employee,
                tax_year=pay_period.tax_year,
            )
            existing_run = balance_service.get_existing_vacation_pay_run_for_period(
                employee=employee,
                pay_period=pay_period,
            )
            return JsonResponse(
                {
                    "ok": True,
                    "earned": str(balance["earned"]),
                    "paid": str(balance["paid"]),
                    "balance": str(balance["balance"]),
                    "has_existing_vacation_run": existing_run is not None,
                    "existing_run_number": existing_run.run_number if existing_run else "",
                }
            )
        except Exception as exc:
            return JsonResponse({"ok": False, "message": str(exc)}, status=400)


# ----------------------------------------------------------------------------
# Admin for pay stubs
# ----------------------------------------------------------------------------
@admin.register(PayStub, site=accounting_admin_site)
class PayStubAdmin(admin.ModelAdmin):
    """Read-only payroll calculation output and audit detail."""

    list_display = (
        "pay_run",
        "employee",
        "gross_salary",
        "total_employee_deductions",
        "net_pay",
        "actual_paid",
        "net_salary_payable",
        "total_remittance_due",
        "admin_actions",
        "pay_type",
        "pay_stub_emailed_at",
        "payment_confirmation_emailed_at",
    )
    list_filter = ("pay_run__pay_period__tax_year", "pay_run__status")
    search_fields = (
        "employee__display_name",
        "employee__legal_first_name",
        "employee__legal_last_name",
        "payment_reference",
        "payment_note",
    )

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Actions")
    def admin_actions(self, obj):
        if not obj or not obj.id:
            return "-"
        return format_html(
            '<a class="button" href="{}">PDF</a> '
            '<a class="button" href="{}">Compare Calculation</a>',
            reverse("accounting_admin:accounting_paystub_pdf", args=[obj.id]),
            reverse("accounting_admin:accounting_paystub_compare", args=[obj.id]),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/pdf/",
                self.admin_site.admin_view(self.pay_stub_pdf_view),
                name="accounting_paystub_pdf",
            ),
            path(
                "<int:object_id>/compare/",
                self.admin_site.admin_view(self.pay_stub_compare_view),
                name="accounting_paystub_compare",
            ),
        ]
        return custom_urls + urls

    def pay_stub_pdf_view(self, request, object_id):
        pay_stub = self.get_object(request, object_id)
        try:
            if is_vacation_pay_stub(pay_stub=pay_stub):
                content = VacationPayPDFService().build_pdf(pay_stub=pay_stub)
                filename = (
                    f"vacation_pay_statement_{pay_stub.pay_run.run_number}_{pay_stub.employee.id}.pdf"
                )
            else:
                content = PayStubPDFService().build_pdf(pay_stub=pay_stub)
                filename = f"pay_stub_{pay_stub.pay_run.run_number}_{pay_stub.employee.id}.pdf"

            response = HttpResponse(content, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as exc:
            self.message_user(
                request,
                f"Pay stub PDF generation failed: {exc}",
                level=messages.ERROR,
            )
            return redirect(
                reverse("accounting_admin:accounting_paystub_change", args=[pay_stub.id])
            )

    def pay_stub_compare_view(self, request, object_id):
        pay_stub = self.get_object(request, object_id)
        payload = PayrollComparisonService().compare_pay_stub(pay_stub=pay_stub)
        return TemplateResponse(
            request,
            "admin/accounting/payroll/pay_stub_compare.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Payroll Calculation Comparison - {pay_stub.employee.display_name}",
                "payload": payload,
                "opts": self.model._meta,
            },
        )


# ----------------------------------------------------------------------------
# Admin for remittances
# ----------------------------------------------------------------------------
@admin.register(PayrollRemittance, site=accounting_admin_site)
class PayrollRemittanceAdmin(admin.ModelAdmin):
    """Service-backed CRA remittance record."""

    list_display = (
        "pay_run",
        "due_date",
        "status",
        "total_due",
        "total_paid",
        "paid_on",
        "payment_reference",
        "admin_actions",
    )
    list_filter = ("status", "due_date")
    search_fields = ("pay_run__run_number", "payment_reference", "note")
    readonly_fields = (
        "pay_run",
        "status",
        "employee_cpp",
        "employer_cpp",
        "employee_cpp2",
        "employer_cpp2",
        "employee_ei",
        "employer_ei",
        "federal_income_tax",
        "provincial_income_tax",
        "total_due",
        "total_paid",
        "paid_on",
        "payment_reference",
        "journal_entry",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == PayrollRemittance.STATUS_PAID:
            readonly.extend(("due_date", "note"))
        return tuple(dict.fromkeys(readonly))

    @admin.display(description="Next step")
    def admin_actions(self, obj):
        if not obj or not obj.id:
            return "-"

        if obj.status in {
            PayrollRemittance.STATUS_DRAFT,
            PayrollRemittance.STATUS_READY,
        } and not obj.journal_entry_id:
            return format_html(
                '<a class="button" href="{}">Record CRA Payment</a>',
                reverse(
                    "accounting_admin:accounting_payrollremittance_record_payment",
                    args=[obj.id],
                ),
            )

        return format_html(
            '<a class="button" href="{}">Open Pay Run</a>',
            reverse("accounting_admin:accounting_payrun_change", args=[obj.pay_run_id]),
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:object_id>/record-payment/",
                self.admin_site.admin_view(self.record_payment_view),
                name="accounting_payrollremittance_record_payment",
            ),
        ]
        return custom_urls + urls

    def record_payment_view(self, request, object_id):
        remittance = self.get_object(request, object_id)

        if request.method == "POST":
            form = RecordPayrollRemittancePaymentAdminForm(request.POST)
            if form.is_valid():
                try:
                    selected_bank = form.cleaned_data["bank_account_code"]
                    journal_entry = PayrollRemittanceService().post_payment(
                        remittance=remittance,
                        paid_on=form.cleaned_data["paid_on"],
                        payment_reference=form.cleaned_data["payment_reference"],
                        bank_account_code=selected_bank.ledger_account.code,
                        created_by=request.user,
                        approved_by=request.user,
                    )
                    self.message_user(
                        request,
                        f"CRA remittance payment posted: {journal_entry.entry_number}",
                        level=messages.SUCCESS,
                    )
                    return redirect(
                        reverse(
                            "accounting_admin:accounting_payrun_change",
                            args=[remittance.pay_run_id],
                        )
                    )
                except Exception as exc:
                    self.message_user(
                        request,
                        f"CRA remittance payment failed: {exc}",
                        level=messages.ERROR,
                    )
        else:
            form = RecordPayrollRemittancePaymentAdminForm(
                initial={
                    "paid_on": timezone.localdate(),
                    "payment_reference": (
                        f"CRA Payroll Remittance - "
                        f"{remittance.pay_run.pay_period.end_date.strftime('%B %Y')}"
                    ),
                }
            )

        return TemplateResponse(
            request,
            "admin/accounting/payroll/record_remittance_payment.html",
            {
                **self.admin_site.each_context(request),
                "title": f"Record CRA Remittance Payment - {remittance.pay_run.run_number}",
                "form": form,
                "remittance": remittance,
                "opts": self.model._meta,
            },
        )


# ----------------------------------------------------------------------------
# Admin for payroll leaves
# ----------------------------------------------------------------------------
@admin.register(PayrollLeavePolicy, site=accounting_admin_site)
class PayrollLeavePolicyAdmin(admin.ModelAdmin):
    """
    Admin for leave policies.
    """

    list_display = (
        "code",
        "name",
        "leave_type",
        "province",
        "is_paid",
        "is_active",
    )
    list_filter = ("leave_type", "province", "is_paid", "is_active")
    search_fields = ("code", "name", "note")
    readonly_fields = ("created_at", "updated_at")


# ----------------------------------------------------------------------------
# Admin for leave balances
# ----------------------------------------------------------------------------
@admin.register(PayrollLeaveBalance, site=accounting_admin_site)
class PayrollLeaveBalanceAdmin(admin.ModelAdmin):
    """
    Admin for leave balances.
    """

    list_display = (
        "employee",
        "policy",
        "year",
        "opening_hours",
        "accrued_hours",
        "used_hours",
        "adjusted_hours",
        "closing_hours",
    )
    list_filter = ("year", "policy")
    search_fields = (
        "employee__display_name",
        "policy__code",
        "policy__name",
    )
    readonly_fields = ("updated_at",)


# ----------------------------------------------------------------------------
# Admin for leave entries
# ----------------------------------------------------------------------------
@admin.register(PayrollLeaveEntry, site=accounting_admin_site)
class PayrollLeaveEntryAdmin(admin.ModelAdmin):
    """
    Admin for leave entries.
    """

    list_display = (
        "employee",
        "policy",
        "entry_date",
        "entry_type",
        "hours",
        "pay_stub",
    )
    list_filter = ("entry_type", "entry_date", "policy")
    search_fields = (
        "employee__display_name",
        "policy__code",
        "policy__name",
        "note",
    )
    readonly_fields = ("created_at",)
    

# ----------------------------------------------------------------------------
# PayrollWorkSummary Admin
# ----------------------------------------------------------------------------
@admin.register(PayrollWorkSummary, site=accounting_admin_site)
class PayrollWorkSummaryAdmin(admin.ModelAdmin):
    """
    Admin for summarized hourly work records.
    """

    list_display = (
        "employee",
        "pay_period",
        "regular_hours",
        "daily_overtime_hours",
        "weekly_overtime_hours",
        "double_time_hours",
        "total_hours",
        "source_app",
        "status",
        "approved_at",
    )
    list_filter = ("status", "pay_period", "source_app")
    search_fields = (
        "employee__display_name",
        "employee__legal_first_name",
        "employee__legal_last_name",
        "source_ref",
        "note",
    )
    readonly_fields = ("created_at", "updated_at", "approved_by", "approved_at")