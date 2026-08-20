# apps/communication/admin/delivery.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.communication.models import (
    EmailCampaignDailyMetric,
    EmailEvent,
    EmailLog,
)


class ReadOnlyCommunicationAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [
            field.name
            for field in self.model._meta.fields
        ]


@admin.register(EmailLog)
class EmailLogAdmin(ReadOnlyCommunicationAdmin):
    list_display = (
        "campaign_link",
        "email",
        "status",
        "provider",
        "sent_at",
        "delivered_at",
        "opened",
        "clicked",
        "open_count",
        "click_count",
    )
    list_filter = (
        "status",
        "provider",
        "opened",
        "clicked",
        "sent_at",
    )
    search_fields = (
        "email",
        "provider_message_id",
        "user__username",
        "user__email",
        "campaign__title",
    )
    date_hierarchy = "sent_at"
    list_select_related = (
        "campaign",
        "user",
        "external_contact",
    )

    @admin.display(description="Campaign")
    def campaign_link(self, obj):
        url = reverse(
            "admin:communication_emailcampaign_change",
            args=[obj.campaign_id],
        )

        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.campaign.title,
        )


@admin.register(EmailEvent)
class EmailEventAdmin(ReadOnlyCommunicationAdmin):
    list_display = (
        "delivery",
        "event_type",
        "occurred_at",
        "provider_event_id",
        "url",
    )
    list_filter = (
        "event_type",
        "occurred_at",
    )
    search_fields = (
        "delivery__email",
        "provider_event_id",
        "dedupe_key",
        "url",
    )
    date_hierarchy = "occurred_at"
    list_select_related = (
        "delivery",
    )


@admin.register(EmailCampaignDailyMetric)
class EmailCampaignDailyMetricAdmin(ReadOnlyCommunicationAdmin):
    list_display = (
        "campaign",
        "date",
        "sent",
        "delivered",
        "opens",
        "unique_opens",
        "clicks",
        "unique_clicks",
        "unsubscribes",
        "bounced",
        "complaints",
        "failed",
    )
    list_filter = (
        "date",
    )
    search_fields = (
        "campaign__title",
    )
    date_hierarchy = "date"
    list_select_related = (
        "campaign",
    )