# apps/notifications/admin/preference_admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django.contrib import admin

from apps.notifications.models import UserNotificationPreference


@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notification_type",
        "enabled",
        "channels_mask",
    )

    list_filter = (
        "notification_type",
        "enabled",
    )

    search_fields = (
        "user__username",
        "user__email",
    )

    list_editable = (
        "enabled",
    )

    list_select_related = (
        "user",
    )

    ordering = (
        "user",
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                "user",
                "notification_type",
            )

        return ()