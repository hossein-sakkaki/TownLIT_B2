# apps/notifications/admin/campaign_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from urllib.parse import urlencode

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.notifications.admin.forms import NotificationCampaignAdminForm
from apps.notifications.campaigns.audience import estimate_campaign_audience
from apps.notifications.campaigns.publisher import (
    queue_campaign,
    send_campaign_preview_to_user,
)
from apps.notifications.models import (
    NotificationCampaign,
    NotificationCampaignDelivery,
)


@admin.register(NotificationCampaign)
class NotificationCampaignAdmin(admin.ModelAdmin):
    form = NotificationCampaignAdminForm

    list_display = (
        "id",
        "internal_name",
        "category",
        "audience_summary",
        "channel_summary",
        "status_badge",
        "total_recipients",
        "processed_count",
        "push_sent_count",
        "created_at",
    )

    list_filter = (
        "status",
        "category",
        "audience_type",
        "platform_scope",
        "send_push",
        "send_email",
        ("created_at", admin.DateFieldListFilter),
    )

    search_fields = (
        "internal_name",
        "title",
        "message",
    )

    autocomplete_fields = (
        "selected_users",
    )

    ordering = (
        "-created_at",
    )

    actions = (
        "queue_selected_campaigns",
        "send_test_to_me",
        "duplicate_as_draft",
        "cancel_selected_campaigns",
    )

    readonly_fields = (
        "created_by",
        "status",
        "recipient_estimate",
        "total_recipients",
        "processed_count",
        "in_app_count",
        "push_sent_count",
        "email_queued_count",
        "failed_count",
        "last_error",
        "published_at",
        "completed_at",
        "created_at",
        "updated_at",
        "delivery_records_link",
    )

    fieldsets = (
        (
            "Campaign",
            {
                "fields": (
                    "internal_name",
                    "category",
                    "title",
                    "message",
                )
            },
        ),
        (
            "Audience",
            {
                "description": (
                    "Choose who qualifies for this campaign, then optionally "
                    "limit delivery to a specific platform."
                ),
                "fields": (
                    "audience_type",
                    "platform_scope",
                    "selected_users",
                    "recipient_estimate",
                ),
            },
        ),
        (
            "Delivery",
            {
                "fields": (
                    "send_push",
                    "send_email",
                    "action_type",
                    "action_label",
                    "action_url",
                )
            },
        ),
        (
            "Schedule",
            {
                "fields": (
                    "scheduled_at",
                    "status",
                )
            },
        ),
        (
            "Results",
            {
                "fields": (
                    "total_recipients",
                    "processed_count",
                    "in_app_count",
                    "push_sent_count",
                    "email_queued_count",
                    "failed_count",
                    "last_error",
                    "delivery_records_link",
                    "published_at",
                    "completed_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_by",
                    "created_at",
                    "updated_at",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(
            self.readonly_fields
        )

        if (
            obj
            and obj.status != NotificationCampaign.Status.DRAFT
        ):
            readonly.extend([
                "internal_name",
                "category",
                "title",
                "message",
                "audience_type",
                "platform_scope",
                "selected_users",
                "send_push",
                "send_email",
                "action_type",
                "action_label",
                "action_url",
                "scheduled_at",
            ])

        return tuple(
            dict.fromkeys(readonly)
        )

    @admin.display(description="Audience")
    def audience_summary(self, obj):
        return (
            f"{obj.get_audience_type_display()} "
            f"• {obj.get_platform_scope_display()}"
        )

    @admin.display(description="Channels")
    def channel_summary(self, obj):
        channels = ["In-App"]

        if obj.send_push:
            channels.append("Push")

        if obj.send_email:
            channels.append("Email")

        return " + ".join(
            channels
        )

    @admin.display(description="Status")
    def status_badge(self, obj):
        styles = {
            NotificationCampaign.Status.DRAFT: "#6c757d",
            NotificationCampaign.Status.SCHEDULED: "#6f42c1",
            NotificationCampaign.Status.QUEUED: "#0d6efd",
            NotificationCampaign.Status.SENDING: "#fd7e14",
            NotificationCampaign.Status.SENT: "#198754",
            NotificationCampaign.Status.CANCELLED: "#495057",
            NotificationCampaign.Status.FAILED: "#dc3545",
        }

        color = styles.get(
            obj.status,
            "#6c757d",
        )

        return format_html(
            '<strong style="color:{};">{}</strong>',
            color,
            obj.get_status_display(),
        )

    @admin.display(description="Estimated recipients")
    def recipient_estimate(self, obj):
        if not obj or not obj.pk:
            return "Save the draft to calculate."

        try:
            return estimate_campaign_audience(
                obj
            )
        except Exception:
            return "Unable to calculate."

    @admin.display(description="Delivery records")
    def delivery_records_link(self, obj):
        if not obj or not obj.pk:
            return "-"

        url = reverse(
            "admin:notifications_notificationcampaigndelivery_changelist"
        )

        query = urlencode({
            "campaign__id__exact": obj.id,
        })

        return format_html(
            '<a href="{}?{}">View recipient deliveries</a>',
            url,
            query,
        )

    @admin.action(description="Queue / schedule selected campaigns")
    def queue_selected_campaigns(self, request, queryset):
        queued = 0
        rejected = 0

        for campaign in queryset:
            try:
                queue_campaign(
                    campaign
                )
                queued += 1

            except ValidationError as error:
                rejected += 1
                self.message_user(
                    request,
                    f"{campaign.internal_name}: {error}",
                    level=messages.ERROR,
                )

        if queued:
            self.message_user(
                request,
                f"{queued} campaign(s) queued or scheduled.",
                level=messages.SUCCESS,
            )

        if rejected and not queued:
            self.message_user(
                request,
                "No campaign was queued.",
                level=messages.WARNING,
            )

    @admin.action(description="Send selected campaign as a test to me")
    def send_test_to_me(self, request, queryset):
        campaigns = list(
            queryset[:2]
        )

        if len(campaigns) != 1:
            self.message_user(
                request,
                "Select exactly one campaign for a test send.",
                level=messages.WARNING,
            )
            return

        campaign = campaigns[0]

        try:
            result = send_campaign_preview_to_user(
                campaign,
                request.user,
            )

            channels = ["In-App"]

            if result.get("apns_sent"):
                channels.append("APNs")

            if result.get("firebase_sent"):
                channels.append("FCM")

            if result.get("email_queued"):
                channels.append("Email")

            self.message_user(
                request,
                "Test sent: " + ", ".join(channels),
                level=messages.SUCCESS,
            )

        except Exception as error:
            self.message_user(
                request,
                f"Test failed: {error}",
                level=messages.ERROR,
            )

    @admin.action(description="Duplicate selected campaigns as Draft")
    def duplicate_as_draft(self, request, queryset):
        created = 0

        for campaign in queryset:
            selected_user_ids = list(
                campaign.selected_users.values_list(
                    "id",
                    flat=True,
                )
            )

            campaign.pk = None
            campaign.id = None
            campaign.internal_name = f"{campaign.internal_name} (Copy)"
            campaign.status = NotificationCampaign.Status.DRAFT
            campaign.scheduled_at = None
            campaign.total_recipients = 0
            campaign.processed_count = 0
            campaign.in_app_count = 0
            campaign.push_sent_count = 0
            campaign.email_queued_count = 0
            campaign.failed_count = 0
            campaign.last_error = ""
            campaign.published_at = None
            campaign.completed_at = None
            campaign.created_by = request.user
            campaign.save()

            if selected_user_ids:
                campaign.selected_users.set(
                    selected_user_ids
                )

            created += 1

        self.message_user(
            request,
            f"{created} draft copy/copies created.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Cancel selected campaigns")
    def cancel_selected_campaigns(self, request, queryset):
        cancellable = queryset.filter(
            status__in=[
                NotificationCampaign.Status.SCHEDULED,
                NotificationCampaign.Status.QUEUED,
                NotificationCampaign.Status.SENDING,
            ]
        )

        updated = cancellable.update(
            status=NotificationCampaign.Status.CANCELLED,
            completed_at=timezone.now(),
        )

        self.message_user(
            request,
            f"{updated} campaign(s) cancelled.",
            level=messages.SUCCESS,
        )

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status not in {
            NotificationCampaign.Status.DRAFT,
            NotificationCampaign.Status.CANCELLED,
            NotificationCampaign.Status.FAILED,
        }:
            return False

        return super().has_delete_permission(
            request,
            obj,
        )


@admin.register(NotificationCampaignDelivery)
class NotificationCampaignDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "campaign",
        "user",
        "status",
        "push_sent",
        "email_queued",
        "processed_at",
    )

    list_filter = (
        "status",
        "push_sent",
        "email_queued",
        "campaign",
    )

    search_fields = (
        "user__username",
        "user__email",
        "campaign__internal_name",
    )

    list_select_related = (
        "campaign",
        "user",
        "notification",
    )

    readonly_fields = (
        "campaign",
        "user",
        "notification",
        "status",
        "push_sent",
        "email_queued",
        "error_message",
        "created_at",
        "processed_at",
    )

    ordering = (
        "-id",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False