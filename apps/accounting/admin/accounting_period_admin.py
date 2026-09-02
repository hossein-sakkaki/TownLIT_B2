# apps/accounting/admin/accounting_period_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin, messages
from django.utils import timezone

from apps.accounting.models import AccountingPeriod

from .site import accounting_admin_site


@admin.register(AccountingPeriod, site=accounting_admin_site)
class AccountingPeriodAdmin(admin.ModelAdmin):
    """
    Accounting period control.

    Locked periods are final from the Admin UI. Reopening a locked period must
    never be an ordinary bulk action.
    """

    list_display = (
        "code",
        "fiscal_year_label",
        "period_type",
        "start_date",
        "end_date",
        "status",
        "closed_at",
        "locked_at",
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
    ordering = ("start_date", "id")
    list_per_page = 50
    actions = (
        "mark_open",
        "mark_closed",
        "mark_locked",
    )

    fieldsets = (
        (
            "Period",
            {
                "fields": (
                    "code",
                    "name",
                    "fiscal_year_label",
                    "period_type",
                    "start_date",
                    "end_date",
                    "status",
                    "note",
                ),
            },
        ),
        (
            "Close / Lock Audit",
            {
                "fields": (
                    "closed_at",
                    "closed_by",
                    "locked_at",
                    "locked_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj and obj.status == AccountingPeriod.STATUS_LOCKED:
            readonly.extend(
                [
                    "code",
                    "name",
                    "fiscal_year_label",
                    "period_type",
                    "start_date",
                    "end_date",
                    "status",
                    "note",
                ]
            )

        return tuple(dict.fromkeys(readonly))

    @admin.action(description="Reopen selected CLOSED periods")
    def mark_open(self, request, queryset):
        updated = 0
        skipped = 0

        for period in queryset:
            if period.status != AccountingPeriod.STATUS_CLOSED:
                skipped += 1
                continue

            period.status = AccountingPeriod.STATUS_OPEN
            period.closed_at = None
            period.closed_by = None
            period.save(
                update_fields=(
                    "status",
                    "closed_at",
                    "closed_by",
                    "updated_at",
                )
            )
            updated += 1

        if updated:
            self.message_user(
                request,
                f"{updated} closed period(s) reopened.",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"{skipped} period(s) skipped. Locked periods cannot be reopened here.",
                level=messages.WARNING,
            )

    @admin.action(description="Close selected OPEN periods")
    def mark_closed(self, request, queryset):
        updated = 0
        skipped = 0

        for period in queryset:
            if period.status != AccountingPeriod.STATUS_OPEN:
                skipped += 1
                continue

            period.status = AccountingPeriod.STATUS_CLOSED
            period.closed_at = timezone.now()
            period.closed_by = request.user
            period.save(
                update_fields=(
                    "status",
                    "closed_at",
                    "closed_by",
                    "updated_at",
                )
            )
            updated += 1

        if updated:
            self.message_user(
                request,
                f"{updated} open period(s) closed.",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"{skipped} period(s) skipped because they were not OPEN.",
                level=messages.WARNING,
            )

    @admin.action(description="Lock selected CLOSED periods")
    def mark_locked(self, request, queryset):
        updated = 0
        skipped = 0

        for period in queryset:
            if period.status != AccountingPeriod.STATUS_CLOSED:
                skipped += 1
                continue

            period.status = AccountingPeriod.STATUS_LOCKED
            period.locked_at = timezone.now()
            period.locked_by = request.user
            period.save(
                update_fields=(
                    "status",
                    "locked_at",
                    "locked_by",
                    "updated_at",
                )
            )
            updated += 1

        if updated:
            self.message_user(
                request,
                f"{updated} closed period(s) locked.",
                level=messages.SUCCESS,
            )

        if skipped:
            self.message_user(
                request,
                f"{skipped} period(s) skipped. Only CLOSED periods can be locked.",
                level=messages.WARNING,
            )
