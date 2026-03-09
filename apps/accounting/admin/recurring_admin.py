# apps/accounting/admin/recurring_admin.py

from django.contrib import admin, messages
from django.utils import timezone

from apps.accounting.models import RecurringJournalTemplate
from apps.accounting.services.recurring_service import run_recurring_template
from .site import accounting_admin_site


@admin.register(RecurringJournalTemplate, site=accounting_admin_site)
class RecurringJournalTemplateAdmin(admin.ModelAdmin):
    """
    Admin for recurring accounting templates.
    """

    list_display = (
        "code",
        "name",
        "template_type",
        "frequency",
        "status",
        "next_run_date",
        "last_run_date",
        "is_active",
        "created_at",
    )
    list_filter = (
        "template_type",
        "frequency",
        "status",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
        "description",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_run_date",
    )
    actions = [
        "run_selected_templates_now",
    ]

    @admin.action(description="Run selected recurring templates now")
    def run_selected_templates_now(self, request, queryset):
        """
        Execute recurring templates immediately.
        """

        updated = 0
        today = timezone.localdate()

        for template in queryset:
            try:
                run_recurring_template(
                    template=template,
                    run_date=today,
                    created_by=request.user,
                    approved_by=request.user,
                )
                updated += 1
            except Exception:
                continue

        self.message_user(
            request,
            f"{updated} recurring template(s) executed.",
            level=messages.SUCCESS,
        )