# apps/notifications/admin/notification_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django.contrib import admin
from django.utils.html import format_html

from apps.notifications.models import Notification, NotificationLog


class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    fields = (
        "recipient",
        "sent_at",
        "read_at",
    )
    readonly_fields = fields
    can_delete = False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "notification_type",
        "campaign",
        "short_title",
        "short_message",
        "created_at",
        "is_read",
        "link_preview",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "campaign",
        ("created_at", admin.DateFieldListFilter),
    )

    search_fields = (
        "user__username",
        "user__email",
        "actor__username",
        "title",
        "message",
        "campaign__internal_name",
    )

    list_select_related = (
        "user",
        "actor",
        "campaign",
    )

    readonly_fields = (
        "user",
        "actor",
        "campaign",
        "title",
        "notification_type",
        "message",
        "created_at",
        "is_read",
        "read_at",
        "target_content_type",
        "target_object_id",
        "action_content_type",
        "action_object_id",
        "link",
        "action_label",
        "metadata",
        "dedupe_key",
    )

    inlines = (
        NotificationLogInline,
    )

    ordering = (
        "-created_at",
    )

    @admin.display(description="Title")
    def short_title(self, obj):
        value = obj.title or "-"
        return value[:60]

    @admin.display(description="Message")
    def short_message(self, obj):
        return (
            obj.message[:70] + "..."
            if len(obj.message) > 70
            else obj.message
        )

    @admin.display(description="Link")
    def link_preview(self, obj):
        if not obj.link:
            return "-"

        return format_html(
            '<a href="{}" target="_blank">Open</a>',
            obj.link,
        )

    def has_add_permission(self, request):
        # Notifications must come from services or campaigns.
        return False