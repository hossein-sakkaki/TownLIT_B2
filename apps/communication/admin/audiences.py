# apps/communication/admin/audiences.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.contrib import admin

from apps.communication.forms import (
    EmailAudienceAdminForm,
    EmailAudienceRuleAdminForm,
)
from apps.communication.models import (
    EmailAudience,
    EmailAudienceRule,
    EmailSubscriptionPreference,
    EmailTopic,
    UnsubscribedUser,
)


class EmailAudienceRuleInline(admin.TabularInline):
    model = EmailAudienceRule
    form = EmailAudienceRuleAdminForm
    extra = 0
    fields = (
        "field",
        "operator",
        "rule_value",
        "negate",
        "sort_order",
        "is_active",
    )


@admin.register(EmailAudience)
class EmailAudienceAdmin(admin.ModelAdmin):
    form = EmailAudienceAdminForm
    inlines = [EmailAudienceRuleInline]

    list_display = (
        "name",
        "kind",
        "preset_key",
        "estimated_count",
        "respect_unsubscribe",
        "is_active",
        "updated_at",
    )
    list_filter = (
        "kind",
        "respect_unsubscribe",
        "is_active",
    )
    search_fields = (
        "name",
        "description",
    )
    autocomplete_fields = (
        "users",
        "external_contacts",
    )
    readonly_fields = (
        "estimated_count",
        "last_estimated_at",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "Audience",
            {
                "fields": (
                    "name",
                    "description",
                    "kind",
                    "match_type",
                    "preset_key",
                    "is_active",
                ),
            },
        ),
        (
            "Manual Members",
            {
                "fields": (
                    "users",
                    "external_contacts",
                ),
            },
        ),
        (
            "Delivery Rules",
            {
                "fields": (
                    "respect_unsubscribe",
                ),
            },
        ),
        (
            "Estimate",
            {
                "fields": (
                    "estimated_count",
                    "last_estimated_at",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(EmailTopic)
class EmailTopicAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "allow_unsubscribe",
        "is_active",
        "sort_order",
    )
    list_editable = (
        "allow_unsubscribe",
        "is_active",
        "sort_order",
    )
    search_fields = (
        "name",
        "slug",
        "description",
    )
    ordering = (
        "sort_order",
        "name",
    )


@admin.register(EmailSubscriptionPreference)
class EmailSubscriptionPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "user",
        "topic",
        "status",
        "source",
        "updated_at",
    )
    list_filter = (
        "status",
        "source",
        "topic",
    )
    search_fields = (
        "email",
        "user__email",
        "user__username",
    )
    autocomplete_fields = (
        "user",
        "topic",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(UnsubscribedUser)
class UnsubscribedUserAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "user",
        "scope",
        "source",
        "unsubscribed_at",
    )
    list_filter = (
        "scope",
        "source",
        "unsubscribed_at",
    )
    search_fields = (
        "email",
        "user__email",
        "user__username",
    )
    readonly_fields = (
        "unsubscribed_at",
    )