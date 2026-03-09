# apps/accounting/admin/document_admin.py

from django.contrib import admin

from apps.accounting.models import AccountingDocument
from .site import accounting_admin_site


@admin.register(AccountingDocument, site=accounting_admin_site)
class AccountingDocumentAdmin(admin.ModelAdmin):
    """
    Admin for accounting documents and attachments.
    """

    list_display = (
        "title",
        "document_type",
        "reference",
        "journal_entry",
        "fund",
        "founder_loan",
        "uploaded_by",
        "is_active",
        "created_at",
    )
    list_filter = (
        "document_type",
        "is_active",
        "created_at",
    )
    search_fields = (
        "title",
        "reference",
        "description",
        "journal_entry__entry_number",
        "fund__code",
        "fund__name",
        "founder_loan__lender_display_name",
    )
    raw_id_fields = (
        "journal_entry",
        "fund",
        "founder_loan",
        "uploaded_by",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    def save_model(self, request, obj, form, change):
        """
        Auto-fill uploader on first save.
        """

        if not obj.pk and not obj.uploaded_by_id:
            obj.uploaded_by = request.user

        super().save_model(request, obj, form, change)