# apps/accounting/admin/bank_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.accounting.models import Account, BankAccount, BankInstitution

from .site import accounting_admin_site


@admin.register(BankInstitution, site=accounting_admin_site)
class BankInstitutionAdmin(admin.ModelAdmin):
    """
    Financial institutions and payment processors.
    """

    list_display = (
        "code",
        "name",
        "institution_type",
        "country",
        "swift_code",
        "is_active",
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
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    ordering = ("name",)
    list_per_page = 50


@admin.register(BankAccount, site=accounting_admin_site)
class BankAccountAdmin(admin.ModelAdmin):
    """
    Real bank/payment accounts linked to the accounting ledger.

    Financial opening balances are never maintained here. Ledger truth comes
    from posted JournalEntries and Transactions.
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
        "banking_link",
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
    autocomplete_fields = ("ledger_account",)
    readonly_fields = (
        "institution_name_snapshot",
        "opening_balance_policy",
        "created_at",
        "updated_at",
    )
    list_select_related = ("institution", "ledger_account")
    ordering = ("code",)
    list_per_page = 50

    fieldsets = (
        (
            "Bank Account",
            {
                "fields": (
                    "code",
                    "name",
                    "institution",
                    "account_type",
                    "account_holder_name",
                    "account_number_masked",
                ),
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
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Accounting",
            {
                "fields": (
                    "ledger_account",
                    "currency",
                    "status",
                    "is_primary",
                    "is_active",
                    "opening_balance_policy",
                ),
                "description": (
                    "The linked ledger account is the accounting source of truth. "
                    "Do not maintain a separate financial opening balance here."
                ),
            },
        ),
        (
            "Dates & Notes",
            {
                "fields": (
                    "opened_on",
                    "closed_on",
                    "note",
                ),
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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "ledger_account":
            kwargs["queryset"] = Account.objects.filter(
                account_type=Account.TYPE_ASSET,
                is_active=True,
                allows_posting=True,
            ).order_by("code")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj:
            readonly.extend(
                [
                    "code",
                    "ledger_account",
                ]
            )

        return tuple(dict.fromkeys(readonly))

    @admin.display(description="Opening Balance")
    def opening_balance_policy(self, obj):
        legacy_value = getattr(obj, "opening_balance", 0) if obj else 0

        return format_html(
            '<div style="max-width:720px">'
            '<strong>Ledger-controlled.</strong> '
            'Opening balances must be posted through a balanced journal entry. '
            'The legacy BankAccount opening_balance field is not used as financial truth.'
            '<br><span style="color:#667085">Legacy stored value: {}</span>'
            '</div>',
            legacy_value,
        )

    @admin.display(description="Banking")
    def banking_link(self, obj):
        url = reverse("accounting_admin:accounting-banking-workspace")
        return format_html(
            '<a class="button" href="{}?bank_account={}">Open workspace</a>',
            url,
            obj.id,
        )

    def has_delete_permission(self, request, obj=None):
        return False
