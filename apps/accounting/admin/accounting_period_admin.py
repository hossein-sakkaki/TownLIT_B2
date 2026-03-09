# apps/accounting/admin/accounting_period_admin.py

from django.contrib import admin, messages
from django.utils import timezone

from apps.accounting.models import AccountingPeriod
from .site import accounting_admin_site


@admin.register(AccountingPeriod, site=accounting_admin_site)
class AccountingPeriodAdmin(admin.ModelAdmin):
    """
    Admin for accounting periods.
    """

    list_display = (
        "code",
        "name",
        "fiscal_year_label",
        "period_type",
        "start_date",
        "end_date",
        "status",
        "closed_at",
        "locked_at",
        "created_at",
    )
    list_filter = (
        "status",
        "period_type",
        "fiscal_year_label",
    )
    search_fields = (
        "code",
        "name",
        "fiscal_year_label",
        "note",
    )
    readonly_fields = (
        "closed_at",
        "closed_by",
        "locked_at",
        "locked_by",
        "created_at",
        "updated_at",
    )
    ordering = ("start_date",)
    actions = [
        "mark_open",
        "mark_closed",
        "mark_locked",
    ]

    @admin.action(description="Mark selected periods as OPEN")
    def mark_open(self, request, queryset):
        updated = 0

        for period in queryset:
            period.status = AccountingPeriod.STATUS_OPEN
            period.closed_at = None
            period.closed_by = None
            period.locked_at = None
            period.locked_by = None
            period.save(
                update_fields=[
                    "status",
                    "closed_at",
                    "closed_by",
                    "locked_at",
                    "locked_by",
                    "updated_at",
                ]
            )
            updated += 1

        self.message_user(
            request,
            f"{updated} period(s) marked as OPEN.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected periods as CLOSED")
    def mark_closed(self, request, queryset):
        updated = 0

        for period in queryset:
            period.status = AccountingPeriod.STATUS_CLOSED
            period.closed_at = timezone.now()
            period.closed_by = request.user
            period.save(
                update_fields=[
                    "status",
                    "closed_at",
                    "closed_by",
                    "updated_at",
                ]
            )
            updated += 1

        self.message_user(
            request,
            f"{updated} period(s) marked as CLOSED.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected periods as LOCKED")
    def mark_locked(self, request, queryset):
        updated = 0

        for period in queryset:
            period.status = AccountingPeriod.STATUS_LOCKED
            period.locked_at = timezone.now()
            period.locked_by = request.user
            period.save(
                update_fields=[
                    "status",
                    "locked_at",
                    "locked_by",
                    "updated_at",
                ]
            )
            updated += 1

        self.message_user(
            request,
            f"{updated} period(s) marked as LOCKED.",
            level=messages.SUCCESS,
        )