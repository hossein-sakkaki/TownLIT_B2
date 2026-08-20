# apps/communication/admin/legacy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.contrib import admin, messages

from apps.communication.models import (
    DraftCampaign,
    ExternalContact,
    ExternalEmailCampaign,
    ScheduledEmail,
)
from apps.communication.services import send_external_email_campaign


@admin.register(ExternalContact)
class ExternalContactAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "name",
        "family",
        "country",
        "source",
        "is_active",
        "is_unsubscribed",
        "became_user",
        "last_contacted_at",
        "created_at",
    )
    list_filter = (
        "country",
        "gender",
        "source",
        "is_active",
        "is_unsubscribed",
        "became_user",
    )
    search_fields = (
        "email",
        "name",
        "family",
        "phone",
    )
    readonly_fields = (
        "created_at",
    )
    ordering = (
        "-created_at",
    )


@admin.register(ExternalEmailCampaign)
class ExternalEmailCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "created_by",
        "created_at",
        "is_sent",
        "sent_at",
    )
    readonly_fields = (
        "created_at",
        "sent_at",
        "is_sent",
    )
    search_fields = (
        "title",
        "subject",
    )
    actions = (
        "send_legacy_external_campaigns",
    )

    @admin.action(description="Send selected legacy external campaigns")
    def send_legacy_external_campaigns(self, request, queryset):
        for campaign in queryset:
            if campaign.is_sent:
                continue

            try:
                result = send_external_email_campaign(campaign)

                self.message_user(
                    request,
                    (
                        f"{campaign.title}: "
                        f"{result['sent']} sent, "
                        f"{result['skipped_duplicates']} skipped, "
                        f"{result['failed_saves']} failed."
                    ),
                    messages.SUCCESS,
                )

            except Exception as error:
                self.message_user(
                    request,
                    f"{campaign.title}: {error}",
                    messages.ERROR,
                )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)


@admin.register(ScheduledEmail)
class ScheduledEmailAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "run_at",
        "is_sent",
        "executed_at",
        "created_at",
    )
    list_filter = (
        "is_sent",
    )
    search_fields = (
        "campaign__title",
    )
    readonly_fields = (
        "campaign",
        "run_at",
        "created_by",
        "created_at",
        "executed_at",
        "is_sent",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DraftCampaign)
class DraftCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "last_edited",
    )
    search_fields = (
        "campaign__title",
        "notes",
    )
    readonly_fields = (
        "campaign",
        "notes",
        "last_edited",
    )

    def has_add_permission(self, request):
        return False