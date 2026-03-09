# apps/accounting/admin/account_admin.py

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html

from apps.accounting.models import AccountCategory, Account
from .site import accounting_admin_site


@admin.register(AccountCategory, site=accounting_admin_site)
class AccountCategoryAdmin(admin.ModelAdmin):
    """
    Admin for account categories.
    """

    list_display = (
        "name",
        "code_prefix",
        "sort_order",
        "is_active",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "code_prefix", "description")
    ordering = ("sort_order", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Account, site=accounting_admin_site)
class AccountAdmin(admin.ModelAdmin):
    """
    Admin for chart of accounts.
    """

    list_display = (
        "code",
        "name",
        "account_type",
        "category",
        "parent",
        "normal_balance",
        "allows_posting",
        "is_system",
        "is_active",
        "sort_order",
        "ledger_link",
    )
    list_filter = (
        "account_type",
        "category",
        "normal_balance",
        "allows_posting",
        "is_system",
        "is_active",
    )
    search_fields = ("code", "name", "description")
    ordering = ("code",)
    readonly_fields = ("created_at", "updated_at")
    change_form_template = "admin/accounting/change_form_with_reports.html"
    list_select_related = ("category", "parent")
    actions = ("activate_accounts", "deactivate_accounts")

    fieldsets = (
        (
            "Basic Info",
            {
                "fields": (
                    "code",
                    "name",
                    "description",
                    "account_type",
                    "category",
                    "parent",
                )
            },
        ),
        (
            "Behavior",
            {
                "fields": (
                    "normal_balance",
                    "allows_posting",
                    "is_system",
                    "is_active",
                    "sort_order",
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

    @admin.action(description="Activate selected accounts")
    def activate_accounts(self, request, queryset):
        """
        Activate non-system accounts.
        """

        updated = queryset.filter(is_system=False).update(is_active=True)
        skipped = queryset.filter(is_system=True).count()

        self.message_user(
            request,
            f"{updated} account(s) activated. {skipped} system account(s) skipped.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected accounts")
    def deactivate_accounts(self, request, queryset):
        """
        Deactivate non-system accounts.
        """

        updated = queryset.filter(is_system=False).update(is_active=False)
        skipped = queryset.filter(is_system=True).count()

        self.message_user(
            request,
            f"{updated} account(s) deactivated. {skipped} system account(s) skipped.",
            level=messages.SUCCESS,
        )

    @admin.display(description="Ledger")
    def ledger_link(self, obj):
        """
        Shortcut to general ledger export for this account.
        """

        url = reverse("accounting-general-ledger", kwargs={"account_code": obj.code})
        return format_html(
            '<a href="{}?file_format=xlsx" target="_blank">Export Ledger</a>',
            url,
        )

    def change_view(self, request, object_id, form_url="", extra_context=None):
        """
        Add report shortcuts to account change page.
        """

        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)

        if obj:
            extra_context["report_links"] = [
                {
                    "label": "Ledger CSV",
                    "url": f'{reverse("accounting-general-ledger", kwargs={"account_code": obj.code})}?file_format=csv',
                },
                {
                    "label": "Ledger XLSX",
                    "url": f'{reverse("accounting-general-ledger", kwargs={"account_code": obj.code})}?file_format=xlsx',
                },
                {
                    "label": "Ledger PDF",
                    "url": f'{reverse("accounting-general-ledger", kwargs={"account_code": obj.code})}?file_format=pdf',
                },
            ]

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Limit selectable parent accounts.
        """

        if db_field.name == "parent":
            kwargs["queryset"] = Account.objects.filter(
                is_active=True,
                allows_posting=False,
            ).order_by("code")

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        """
        Protect key system fields after creation.
        """

        readonly = list(super().get_readonly_fields(request, obj))

        if obj and obj.is_system:
            readonly.extend(
                [
                    "code",
                    "account_type",
                    "category",
                    "parent",
                    "normal_balance",
                    "allows_posting",
                    "is_system",
                ]
            )

        return readonly

    def has_delete_permission(self, request, obj=None):
        """
        Prevent deleting system accounts.
        """

        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        """
        Run model validation before saving.
        """

        try:
            obj.full_clean()
        except ValidationError as exc:
            form.add_error(None, exc)
            return

        super().save_model(request, obj, form, change)