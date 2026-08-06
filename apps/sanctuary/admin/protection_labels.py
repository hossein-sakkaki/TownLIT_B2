# apps/sanctuary/admin/protection_labels.py

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone

from apps.sanctuary.models import (
    SanctuaryProtectionLabel,
)
from .media_preview import (
    sanctuary_admin_media_panel,
)

from .helpers import (
    admin_link,
    username_link,
)


@admin.register(
    SanctuaryProtectionLabel
)
class SanctuaryProtectionLabelAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "label_type",
        "is_active",
        "applied_by",
        "target_link",
        "applied_at",
        "expires_at",
        "created_by_link",
        "outcome_link",
    )

    list_filter = (
        "label_type",
        "is_active",
        "applied_by",
        "applied_at",
        "expires_at",
    )

    search_fields = (
        "=id",
        "label_type",
        "note",
        "created_by__username",
        "object_id",
    )

    ordering = (
        "-applied_at",
        "-id",
    )

    list_select_related = (
        "content_type",
        "created_by",
        "outcome",
    )

    readonly_fields = (
        "label_type",
        "applied_by",
        "content_type",
        "object_id",
        "outcome",
        "created_by",
        "applied_at",
        "target_link",
        "target_media_preview",
        "created_by_link",
        "outcome_link",
    )

    fieldsets = (
        (
            "Protection label",
            {
                "fields": (
                    "label_type",
                    "is_active",
                    "applied_by",
                    "note",
                    "expires_at",
                ),
            },
        ),
        (
            "Target",
            {
                "fields": (
                    "content_type",
                    "object_id",
                    "target_link",
                    "target_media_preview",
                ),
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "outcome",
                    "outcome_link",
                    "created_by",
                    "created_by_link",
                    "applied_at",
                ),
            },
        ),
    )

    actions = (
        "action_activate",
        "action_deactivate",
        "action_extend_90_days",
        "action_deactivate_if_expired",
    )
    
    @admin.display(
        description="Private media review",
    )
    def target_media_preview(
        self,
        obj,
    ):
        target = getattr(
            obj,
            "content_object",
            None,
        )

        if target is None:
            return "Target unavailable"

        return sanctuary_admin_media_panel(
            target
        )
    

    @admin.display(
        description="Target",
    )
    def target_link(
        self,
        obj,
    ):
        target = getattr(
            obj,
            "content_object",
            None,
        )

        return admin_link(
            target
        )

    @admin.display(
        description="Created by",
        ordering="created_by__username",
    )
    def created_by_link(
        self,
        obj,
    ):
        return username_link(
            obj.created_by
        )

    @admin.display(
        description="Outcome",
        ordering="outcome__id",
    )
    def outcome_link(
        self,
        obj,
    ):
        if not obj.outcome_id:
            return "-"

        return admin_link(
            obj.outcome,
            f"Outcome {obj.outcome_id}",
        )

    @admin.action(
        description="Activate selected labels"
    )
    def action_activate(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            is_active=True
        )

        self.message_user(
            request,
            f"Activated {count} label(s).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Deactivate selected labels"
    )
    def action_deactivate(
        self,
        request,
        queryset,
    ):
        count = queryset.update(
            is_active=False
        )

        self.message_user(
            request,
            f"Deactivated {count} label(s).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description=(
            "Extend selected labels "
            "by 90 days"
        )
    )
    def action_extend_90_days(
        self,
        request,
        queryset,
    ):
        now = timezone.now()
        updated = 0

        for label in queryset:
            baseline = (
                label.expires_at
                if (
                    label.expires_at
                    and label.expires_at > now
                )
                else now
            )

            label.expires_at = (
                baseline
                + timedelta(days=90)
            )

            label.is_active = True

            label.save(
                update_fields=[
                    "expires_at",
                    "is_active",
                ]
            )

            updated += 1

        self.message_user(
            request,
            (
                f"Extended {updated} label(s) "
                "by 90 days."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(
        description=(
            "Deactivate selected labels "
            "that have expired"
        )
    )
    def action_deactivate_if_expired(
        self,
        request,
        queryset,
    ):
        count = (
            queryset
            .filter(
                is_active=True,
                expires_at__isnull=False,
                expires_at__lte=(
                    timezone.now()
                ),
            )
            .update(
                is_active=False
            )
        )

        self.message_user(
            request,
            (
                f"Deactivated {count} "
                "expired label(s)."
            ),
            level=messages.SUCCESS,
        )

    def has_add_permission(
        self,
        request,
    ):
        # Labels should originate from Sanctuary outcomes/services.
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False