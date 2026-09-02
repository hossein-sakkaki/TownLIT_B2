# apps/accounting/admin/journal_entry_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.contrib import admin, messages
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import Account, JournalEntry, Transaction
from apps.accounting.services.period_service import (
    AccountingPeriodError,
    assert_can_post_to_date,
)
from apps.accounting.services.posting_engine import PostingEngine
from apps.accounting.services.workflow_service import (
    approve_entry,
    mark_posted,
    submit_for_approval,
)

from .forms import (
    JournalEntryAdminForm,
    TransactionAdminForm,
    TransactionInlineFormSet,
)
from .site import accounting_admin_site


class SafeJournalEntryAdminForm(JournalEntryAdminForm):
    """
    Validate accounting-period availability before Admin saves the draft.
    """

    def clean(self):
        cleaned_data = super().clean()
        entry_date = cleaned_data.get("entry_date")

        if entry_date:
            try:
                assert_can_post_to_date(entry_date)
            except AccountingPeriodError as exc:
                self.add_error("entry_date", str(exc))

        return cleaned_data


class TransactionInline(admin.TabularInline):
    """
    Editable draft lines and read-only posted audit lines.
    """

    model = Transaction
    form = TransactionAdminForm
    formset = TransactionInlineFormSet
    extra = 2
    ordering = ("line_number", "id")
    fields = (
        "line_number",
        "account",
        "debit",
        "credit",
        "memo",
        "fund_code",
        "budget_code",
        "created_at",
    )
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("account")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "account":
            kwargs["queryset"] = (
                Account.objects.filter(
                    is_active=True,
                    allows_posting=True,
                )
                .select_related("category")
                .order_by("code")
            )

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status != JournalEntry.STATUS_DRAFT:
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != JournalEntry.STATUS_DRAFT:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != JournalEntry.STATUS_DRAFT:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(JournalEntry, site=accounting_admin_site)
class JournalEntryAdmin(admin.ModelAdmin):
    """
    Safe manual journal workspace.

    Drafts remain editable. Posting always goes through PostingEngine.
    Posted entries are immutable audit records.
    """

    form = SafeJournalEntryAdminForm

    list_display = (
        "entry_number",
        "entry_date",
        "status",
        "description_short",
        "reference",
        "source_display",
        "entry_totals",
        "posted_at",
    )
    list_filter = (
        "status",
        "currency",
        "source_app",
        "source_model",
        "entry_date",
    )
    search_fields = (
        "entry_number",
        "description",
        "reference",
        "source_ref",
        "source_app",
        "source_model",
        "internal_note",
    )
    date_hierarchy = "entry_date"
    ordering = ("-entry_date", "-id")
    list_select_related = ("created_by", "approved_by")
    list_per_page = 50

    readonly_fields = (
        "entry_number",
        "posted_at",
        "voided_at",
        "created_at",
        "updated_at",
        "entry_totals",
        "created_by",
        "approved_by",
    )
    inlines = (TransactionInline,)
    actions = (
        "post_draft_entries",
        "submit_selected_for_approval",
        "approve_selected_entries",
    )

    fieldsets = (
        (
            "Journal Entry",
            {
                "fields": (
                    "entry_number",
                    "entry_date",
                    "description",
                    "reference",
                    "status",
                    "currency",
                    "entry_totals",
                ),
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "source_app",
                    "source_model",
                    "source_ref",
                ),
                "classes": ("collapse",),
                "description": (
                    "Integration/source metadata. Leave blank for an ordinary manual journal."
                ),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "internal_note",
                    "created_by",
                    "approved_by",
                    "posted_at",
                    "voided_at",
                    "void_reason",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            total_debit=Sum("transactions__debit"),
            total_credit=Sum("transactions__credit"),
        )

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if db_field.name == "status":
            kwargs["choices"] = (
                (JournalEntry.STATUS_DRAFT, "Draft"),
                (JournalEntry.STATUS_VOID, "Void"),
            )

        return super().formfield_for_choice_field(db_field, request, **kwargs)

    @admin.display(description="Description")
    def description_short(self, obj):
        value = (obj.description or "").strip()
        if len(value) <= 70:
            return value
        return f"{value[:67]}..."

    @admin.display(description="Source")
    def source_display(self, obj):
        if not obj.source_app and not obj.source_model:
            return "Manual"

        source = "/".join(
            value
            for value in (obj.source_app, obj.source_model)
            if value
        )
        return source or "-"

    @admin.display(description="Debit / Credit")
    def entry_totals(self, obj):
        debit = getattr(obj, "total_debit", None)
        credit = getattr(obj, "total_credit", None)

        if debit is None or credit is None:
            totals = obj.transactions.aggregate(
                debit=Sum("debit"),
                credit=Sum("credit"),
            )
            debit = totals["debit"] or 0
            credit = totals["credit"] or 0

        return f"{debit} / {credit}"

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj and obj.status != JournalEntry.STATUS_DRAFT:
            readonly.extend(
                [
                    "entry_date",
                    "description",
                    "reference",
                    "status",
                    "currency",
                    "source_app",
                    "source_model",
                    "source_ref",
                    "internal_note",
                    "void_reason",
                ]
            )

        return tuple(dict.fromkeys(readonly))

    def save_model(self, request, obj, form, change):
        """
        Save draft/void state only. Never post from ModelAdmin.save_model.
        """

        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user

        if obj.status == JournalEntry.STATUS_VOID and not obj.voided_at:
            obj.voided_at = timezone.now()

        super().save_model(request, obj, form, change)

    @admin.action(description="Post selected drafts to ledger")
    def post_draft_entries(self, request, queryset):
        engine = PostingEngine()
        posted = 0
        skipped = 0

        for entry in queryset.order_by("entry_date", "id"):
            if entry.status != JournalEntry.STATUS_DRAFT:
                skipped += 1
                continue

            try:
                posted_entry = engine.post_draft(
                    journal_entry=entry,
                    approved_by=request.user,
                )
                mark_posted(journal_entry=posted_entry)
                posted += 1
            except Exception as exc:
                skipped += 1
                self.message_user(
                    request,
                    f"{entry.entry_number}: {exc}",
                    level=messages.ERROR,
                )

        if posted:
            self.message_user(
                request,
                f"{posted} journal entr{'y' if posted == 1 else 'ies'} posted.",
                level=messages.SUCCESS,
            )

        if skipped and not posted:
            self.message_user(
                request,
                "No selected journal entries were posted.",
                level=messages.WARNING,
            )

    @admin.action(description="Submit selected drafts for approval")
    def submit_selected_for_approval(self, request, queryset):
        updated = 0

        for entry in queryset:
            try:
                submit_for_approval(
                    journal_entry=entry,
                    user=request.user,
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{entry.entry_number}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} journal entr{'y' if updated == 1 else 'ies'} submitted.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Approve selected submitted entries")
    def approve_selected_entries(self, request, queryset):
        updated = 0

        for entry in queryset:
            try:
                approve_entry(
                    journal_entry=entry,
                    user=request.user,
                )
                updated += 1
            except Exception as exc:
                self.message_user(
                    request,
                    f"{entry.entry_number}: {exc}",
                    level=messages.ERROR,
                )

        if updated:
            self.message_user(
                request,
                f"{updated} journal entr{'y' if updated == 1 else 'ies'} approved.",
                level=messages.SUCCESS,
            )
