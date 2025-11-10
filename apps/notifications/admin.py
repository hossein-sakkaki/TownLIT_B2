from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Notification,
    NotificationLog,
    UserNotificationPreference,
)

# --- Inline for Logs ------------------------------------------------------
class NotificationLogInline(admin.TabularInline):
    model = NotificationLog
    extra = 0
    fields = ("recipient", "sent_at", "read_at")
    readonly_fields = ("recipient", "sent_at", "read_at")


# --- Notification Admin ---------------------------------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "actor",
        "notification_type",
        "short_message",
        "created_at",
        "is_read",
        "colored_link",
    )
    list_filter = (
        "notification_type",
        "is_read",
        ("created_at", admin.DateFieldListFilter),
    )
    search_fields = (
        "user__username",
        "actor__username",
        "message",
    )
    readonly_fields = (
        "user",
        "actor",
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
        "dedupe_key",
    )
    inlines = [NotificationLogInline]
    ordering = ("-created_at",)

    # --- Shorten message for display ---
    def short_message(self, obj):
        return (obj.message[:60] + "...") if len(obj.message) > 60 else obj.message
    short_message.short_description = "Message"

    # --- Colored link preview ---
    def colored_link(self, obj):
        if obj.link:
            return format_html("<a href='{}' target='_blank' style='color:#007bff;'>Open</a>", obj.link)
        return "-"
    colored_link.short_description = "Link"


# --- User Preferences Admin ----------------------------------------------
@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notification_type",
        "enabled",
        "channels_mask",
    )
    list_filter = ("notification_type", "enabled")
    search_fields = ("user__username",)
    list_editable = ("enabled",)
    ordering = ("user",)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("user", "notification_type")
        return ()


# --- Notification Log Admin ----------------------------------------------
@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "notification",
        "recipient",
        "sent_at",
        "read_at",
    )
    search_fields = ("recipient__username", "notification__message")
    list_filter = (("sent_at", admin.DateFieldListFilter),)
    ordering = ("-sent_at",)
    readonly_fields = ("notification", "recipient", "sent_at", "read_at")
