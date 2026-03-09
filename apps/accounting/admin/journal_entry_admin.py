# apps/accounting/admin/journal_entry_admin.py

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from apps.accounting.models import JournalEntry, Transaction, Account
from apps.accounting.services.workflow_service import (
    submit_for_approval,
    approve_entry,
    mark_posted,
)
from apps.accounting.services.period_service import (
    assert_can_post_to_date,
    AccountingPeriodError,
)

from .site import accounting_admin_site
from .forms import (
    JournalEntryAdminForm,
    TransactionInlineFormSet,
    TransactionAdminForm,
)


class TransactionInline(admin.TabularInline):
    """
    Inline lines for journal entries.
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
        """
        Load related account efficiently.
        """

        qs = super().get_queryset(request)
        return qs.select_related("account")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """
        Limit inline account choices.
        """

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
        """
        Block inline add for posted or void entries.
        """

        if obj and obj.status in (JournalEntry.STATUS_POSTED, JournalEntry.STATUS_VOID):
            return False
        return super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        """
        Block inline edits for posted or void entries.
        """

        if obj and obj.status in (JournalEntry.STATUS_POSTED, JournalEntry.STATUS_VOID):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """
        Block inline deletion for posted or void entries.
        """

        if obj and obj.status in (JournalEntry.STATUS_POSTED, JournalEntry.STATUS_VOID):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(JournalEntry, site=accounting_admin_site)
class JournalEntryAdmin(admin.ModelAdmin):
    """
    Admin for journal entries.
    """

    form = JournalEntryAdminForm

    list_display = (
        "entry_number",
        "entry_date",
        "status",
        "currency",
        "reference",
        "source_app",
        "source_model",
        "source_ref",
        "posted_at",
        "created_by",
        "entry_totals",
    )
    list_filter = (
        "status",
        "currency",
        "source_app",
        "source_model",
        "entry_date",
        "created_at",
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
    readonly_fields = (
        "entry_number",
        "posted_at",
        "voided_at",
        "created_at",
        "updated_at",
        "entry_totals",
    )
    inlines = [TransactionInline]
    actions = [
        "post_draft_entries",
        "mark_as_void",
        "submit_selected_for_approval",
        "approve_selected_entries",
    ]
    list_select_related = ("created_by", "approved_by")

    fieldsets = (
        (
            "Entry Info",
            {
                "fields": (
                    "entry_number",
                    "entry_date",
                    "description",
                    "reference",
                    "status",
                    "currency",
                    "entry_totals",
                )
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "source_app",
                    "source_model",
                    "source_ref",
                )
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
                )
            },
        ),
    )

    def get_queryset(self, request):
        """
        Prefetch totals efficiently.
        """

        qs = super().get_queryset(request)
        return qs.annotate(
            total_debit=Sum("transactions__debit"),
            total_credit=Sum("transactions__credit"),
        )

    @admin.display(description="Totals")
    def entry_totals(self, obj):
        """
        Show debit and credit totals.
        """

        debit = getattr(obj, "total_debit", None)
        credit = getattr(obj, "total_credit", None)

        if debit is None or credit is None:
            debit = obj.transactions.aggregate(v=Sum("debit"))["v"] or 0
            credit = obj.transactions.aggregate(v=Sum("credit"))["v"] or 0

        return f"D {debit} / C {credit}"

    @admin.action(description="Submit selected draft entries for approval")
    def submit_selected_for_approval(self, request, queryset):
        """
        Submit selected draft entries into approval workflow.
        """

        updated = 0

        for entry in queryset:
            try:
                submit_for_approval(journal_entry=entry, user=request.user)
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} entr{'y' if updated == 1 else 'ies'} submitted for approval.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Approve selected submitted entries")
    def approve_selected_entries(self, request, queryset):
        """
        Approve selected submitted entries.
        """

        updated = 0

        for entry in queryset:
            try:
                approve_entry(journal_entry=entry, user=request.user)
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} entr{'y' if updated == 1 else 'ies'} approved.",
            level=messages.SUCCESS,
        )

    def has_delete_permission(self, request, obj=None):
        """
        Never allow hard delete for journal entries.
        """

        return False

    def save_model(self, request, obj, form, change):
        """
        Auto-fill audit fields, enforce accounting period rules,
        and sync workflow state.
        """

        try:
            assert_can_post_to_date(obj.entry_date)
        except AccountingPeriodError as exc:
            form.add_error("entry_date", ValidationError(str(exc)))
            return

        if not obj.pk and not obj.created_by_id:
            obj.created_by = request.user

        became_posted = obj.status == JournalEntry.STATUS_POSTED and not obj.posted_at
        became_void = obj.status == JournalEntry.STATUS_VOID and not obj.voided_at

        if became_posted:
            obj.posted_at = timezone.now()

        if became_void:
            obj.voided_at = timezone.now()

        super().save_model(request, obj, form, change)

        if obj.status == JournalEntry.STATUS_POSTED:
            mark_posted(journal_entry=obj)

    @admin.action(description="Post selected draft entries")
    def post_draft_entries(self, request, queryset):
        """
        Mark balanced draft entries as posted.
        Respect accounting period lock.
        """

        updated = 0

        for entry in queryset:
            if entry.status != JournalEntry.STATUS_DRAFT:
                continue

            try:
                assert_can_post_to_date(entry.entry_date)
            except AccountingPeriodError:
                continue

            totals = entry.transactions.aggregate(
                debit=Sum("debit"),
                credit=Sum("credit"),
            )
            total_debit = totals["debit"] or 0
            total_credit = totals["credit"] or 0

            if total_debit <= 0 or total_debit != total_credit:
                continue

            entry.status = JournalEntry.STATUS_POSTED
            entry.posted_at = timezone.now()

            if not entry.approved_by_id:
                entry.approved_by = request.user

            entry.save(
                update_fields=[
                    "status",
                    "posted_at",
                    "approved_by",
                    "updated_at",
                ]
            )

            mark_posted(journal_entry=entry)
            updated += 1

        self.message_user(
            request,
            f"{updated} entr{'y' if updated == 1 else 'ies'} posted successfully.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected draft entries as void")
    def mark_as_void(self, request, queryset):
        """
        Void only draft entries.
        """

        updated = 0

        for entry in queryset:
            if entry.status != JournalEntry.STATUS_DRAFT:
                continue

            entry.status = JournalEntry.STATUS_VOID
            entry.voided_at = timezone.now()
            entry.void_reason = entry.void_reason or "Voided from admin action"
            entry.save(
                update_fields=[
                    "status",
                    "voided_at",
                    "void_reason",
                    "updated_at",
                ]
            )
            updated += 1

        self.message_user(
            request,
            f"{updated} draft entr{'y' if updated == 1 else 'ies'} marked as void.",
            level=messages.SUCCESS,
        )

    def get_readonly_fields(self, request, obj=None):
        """
        Lock posted and void entries.
        """

        readonly = list(super().get_readonly_fields(request, obj))

        if obj and obj.status in (JournalEntry.STATUS_POSTED, JournalEntry.STATUS_VOID):
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
                    "created_by",
                    "approved_by",
                    "void_reason",
                ]
            )

        return readonly