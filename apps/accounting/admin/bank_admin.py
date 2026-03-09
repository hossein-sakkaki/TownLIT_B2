# apps/accounting/admin/bank_admin.py

from django.contrib import admin

from apps.accounting.models import BankInstitution, BankAccount
from .site import accounting_admin_site


@admin.register(BankInstitution, site=accounting_admin_site)
class BankInstitutionAdmin(admin.ModelAdmin):
    """
    Admin for financial institutions and payment processors.
    """

    list_display = (
        "code",
        "name",
        "institution_type",
        "country",
        "swift_code",
        "is_active",
        "created_at",
    )
    list_filter = (
        "institution_type",
        "country",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "swift_code",
        "website",
        "support_phone",
        "support_email",
        "note",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    ordering = ("name",)


@admin.register(BankAccount, site=accounting_admin_site)
class BankAccountAdmin(admin.ModelAdmin):
    """
    Admin for real bank/payment accounts.
    """

    list_display = (
        "code",
        "name",
        "institution",
        "account_type",
        "account_number_masked",
        "ledger_account",
        "currency",
        "status",
        "is_primary",
        "is_active",
        "created_at",
    )
    list_filter = (
        "institution",
        "account_type",
        "currency",
        "status",
        "is_primary",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "institution__code",
        "institution__name",
        "account_holder_name",
        "account_number_masked",
        "transit_number",
        "routing_number",
        "iban",
        "ledger_account__code",
        "ledger_account__name",
        "note",
    )
    raw_id_fields = ("ledger_account",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Basic Info",
            {
                "fields": (
                    "code",
                    "name",
                    "institution",
                    "account_type",
                    "account_holder_name",
                    "account_number_masked",
                )
            },
        ),
        (
            "Bank Details",
            {
                "fields": (
                    "transit_number",
                    "routing_number",
                    "iban",
                    "institution_name_snapshot",
                )
            },
        ),
        (
            "Accounting",
            {
                "fields": (
                    "ledger_account",
                    "currency",
                    "opening_balance",
                    "status",
                    "is_primary",
                    "is_active",
                )
            },
        ),
        (
            "Dates and Notes",
            {
                "fields": (
                    "opened_on",
                    "closed_on",
                    "note",
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