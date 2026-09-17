# apps/notifications/admin/log_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django.contrib import admin

from apps.notifications.models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "notification",
        "recipient",
        "sent_at",
        "read_at",
    )

    search_fields = (
        "recipient__username",
        "recipient__email",
        "notification__message",
    )

    list_filter = (
        ("sent_at", admin.DateFieldListFilter),
    )

    list_select_related = (
        "notification",
        "recipient",
    )

    ordering = (
        "-sent_at",
    )

    readonly_fields = (
        "notification",
        "recipient",
        "sent_at",
        "read_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False