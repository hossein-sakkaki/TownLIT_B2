# apps/subscriptions/admin/accounts.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-28.
# Last Update by Hossein Sakkaki on 2026-08-28.
#

from django.contrib import admin

from apps.subscriptions.models import SubscriptionAccount


@admin.register(SubscriptionAccount)
class SubscriptionAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "public_id",
        "status",
        "default_currency",
        "billing_email",
        "created_at",
    )
    list_filter = ("status", "default_currency")
    search_fields = ("public_id", "billing_email")
    readonly_fields = ("public_id", "created_at", "updated_at", "closed_at")
