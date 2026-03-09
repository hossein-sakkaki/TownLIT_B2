# apps/accounting/admin/founder_loan_admin.py

from django.contrib import admin, messages

from apps.accounting.models import FounderLoan
from .site import accounting_admin_site


@admin.register(FounderLoan, site=accounting_admin_site)
class FounderLoanAdmin(admin.ModelAdmin):
    """
    Admin for founder loan business records.
    """

    list_display = (
        "id",
        "lender_display_name",
        "principal_amount",
        "repaid_amount",
        "outstanding_amount_display",
        "currency",
        "status",
        "loan_date",
        "journal_entry",
        "created_at",
    )
    list_filter = (
        "status",
        "currency",
        "loan_date",
        "created_at",
    )
    search_fields = (
        "lender_display_name",
        "description",
        "internal_note",
        "journal_entry__entry_number",
        "journal_entry__reference",
    )
    raw_id_fields = ("lender", "journal_entry")
    readonly_fields = (
        "repaid_amount",
        "outstanding_amount_display",
        "created_at",
        "updated_at",
    )
    ordering = ("-loan_date", "-id")
    list_select_related = ("lender", "journal_entry")
    actions = ("mark_as_cancelled",)

    fieldsets = (
        (
            "Loan Info",
            {
                "fields": (
                    "lender",
                    "lender_display_name",
                    "principal_amount",
                    "repaid_amount",
                    "outstanding_amount_display",
                    "currency",
                    "loan_date",
                    "status",
                )
            },
        ),
        (
            "Details",
            {
                "fields": (
                    "description",
                    "internal_note",
                    "journal_entry",
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

    @admin.action(description="Mark selected loans as cancelled")
    def mark_as_cancelled(self, request, queryset):
        """
        Cancel only open or partial founder loan records.
        """

        eligible = queryset.filter(
            status__in=(
                FounderLoan.STATUS_OPEN,
                FounderLoan.STATUS_PARTIAL,
            )
        )

        updated = eligible.update(status=FounderLoan.STATUS_CANCELLED)
        skipped = queryset.count() - updated

        self.message_user(
            request,
            f"{updated} founder loan record(s) marked as cancelled. "
            f"{skipped} record(s) skipped.",
            level=messages.SUCCESS,
        )

    def get_readonly_fields(self, request, obj=None):
        """
        Lock sensitive fields after creation.
        """

        readonly = list(super().get_readonly_fields(request, obj))

        if obj:
            readonly.extend(
                [
                    "journal_entry",
                    "principal_amount",
                    "loan_date",
                    "lender",
                    "currency",
                ]
            )

        return readonly

    @admin.display(description="Outstanding Amount")
    def outstanding_amount_display(self, obj):
        """
        Show remaining unpaid balance.
        """
        return obj.outstanding_amount

    def has_delete_permission(self, request, obj=None):
        """
        Prevent deleting founder loan records in admin.
        """
        return False