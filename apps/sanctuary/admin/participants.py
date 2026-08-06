# apps/sanctuary/admin/participants.py

from __future__ import annotations

from django.contrib import admin, messages
from django.db import transaction

from apps.sanctuary.forms import (
    SanctuaryParticipantProfileAdminForm,
)
from apps.sanctuary.models import (
    SanctuaryParticipantAudit,
    SanctuaryParticipantProfile,
)
from apps.sanctuary.services.participants import (
    admin_set_eligibility,
)

from .helpers import (
    admin_link,
    username_link,
)


class SanctuaryParticipantAuditInline(
    admin.TabularInline
):
    model = SanctuaryParticipantAudit
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "created_at",
        "action",
        "actor",
        "reason",
    )

    readonly_fields = fields
    ordering = (
        "-created_at",
        "-id",
    )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(
    SanctuaryParticipantProfile
)
class SanctuaryParticipantProfileAdmin(
    admin.ModelAdmin
):
    form = (
        SanctuaryParticipantProfileAdminForm
    )

    inlines = [
        SanctuaryParticipantAuditInline
    ]

    list_display = (
        "id",
        "user_link",
        "is_participant",
        "is_eligible",
        "eligibility_reason_preview",
        "eligible_changed_at",
        "eligible_changed_by_link",
        "updated_at",
    )

    list_filter = (
        "is_participant",
        "is_eligible",
        "updated_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "eligible_reason",
    )

    ordering = (
        "-updated_at",
        "-id",
    )

    list_select_related = (
        "user",
        "eligible_changed_by",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "participant_opted_in_at",
        "participant_opted_out_at",
        "eligible_changed_at",
        "eligible_changed_by",
        "updated_at",
    )

    fieldsets = (
        (
            "User",
            {
                "fields": (
                    "user",
                ),
            },
        ),
        (
            "Participation — user controlled",
            {
                "description": (
                    "Participation normally changes "
                    "through the user's opt-in or "
                    "opt-out flow."
                ),
                "fields": (
                    "is_participant",
                    "participant_opted_in_at",
                    "participant_opted_out_at",
                ),
            },
        ),
        (
            "Eligibility — TownLIT controlled",
            {
                "description": (
                    "Removing eligibility requires "
                    "a reason and is recorded in "
                    "the audit history."
                ),
                "fields": (
                    "is_eligible",
                    "eligible_reason",
                    "eligible_changed_at",
                    "eligible_changed_by",
                ),
            },
        ),
        (
            "Configuration",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "settings",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="User",
        ordering="user__username",
    )
    def user_link(
        self,
        obj,
    ):
        return username_link(
            obj.user
        )

    @admin.display(
        description="Changed by",
        ordering=(
            "eligible_changed_by__username"
        ),
    )
    def eligible_changed_by_link(
        self,
        obj,
    ):
        return username_link(
            obj.eligible_changed_by
        )

    @admin.display(
        description="Eligibility reason",
    )
    def eligibility_reason_preview(
        self,
        obj,
    ):
        value = (
            obj.eligible_reason
            or ""
        ).strip()

        if not value:
            return "-"

        if len(value) <= 80:
            return value

        return (
            value[:77]
            + "..."
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not change:
            super().save_model(
                request,
                obj,
                form,
                change,
            )
            return

        original = (
            SanctuaryParticipantProfile
            .objects
            .select_for_update()
            .get(
                pk=obj.pk
            )
        )

        eligibility_changed = (
            original.is_eligible
            != bool(obj.is_eligible)
        )

        if not eligibility_changed:
            super().save_model(
                request,
                obj,
                form,
                change,
            )
            return

        new_eligibility = bool(
            obj.is_eligible
        )

        reason = (
            obj.eligible_reason
            or ""
        ).strip()

        if (
            not new_eligibility
            and not reason
        ):
            raise ValueError(
                "A reason is required when "
                "removing Sanctuary eligibility."
            )

        with transaction.atomic():
            # Preserve unrelated editable changes first.
            non_eligibility_fields = [
                field_name
                for field_name in form.changed_data
                if field_name
                not in {
                    "is_eligible",
                    "eligible_reason",
                }
            ]

            if non_eligibility_fields:
                for field_name in (
                    non_eligibility_fields
                ):
                    setattr(
                        original,
                        field_name,
                        getattr(
                            obj,
                            field_name,
                        ),
                    )

                original.save(
                    update_fields=(
                        non_eligibility_fields
                    )
                )

            admin_set_eligibility(
                user=obj.user,
                is_eligible=(
                    new_eligibility
                ),
                admin_user=request.user,
                reason=(
                    reason
                    if not new_eligibility
                    else None
                ),
                metadata={
                    "source": "admin_ui",
                },
            )

        obj.refresh_from_db()

        self.message_user(
            request,
            (
                "Sanctuary eligibility was "
                "updated and audited."
            ),
            level=messages.SUCCESS,
        )


@admin.register(
    SanctuaryParticipantAudit
)
class SanctuaryParticipantAuditAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "profile_link",
        "user_link",
        "action",
        "actor_link",
        "reason_preview",
        "created_at",
    )

    list_filter = (
        "action",
        "created_at",
    )

    search_fields = (
        "profile__user__username",
        "profile__user__email",
        "actor__username",
        "reason",
    )

    ordering = (
        "-created_at",
        "-id",
    )

    list_select_related = (
        "profile",
        "profile__user",
        "actor",
    )

    readonly_fields = (
        "profile",
        "action",
        "actor",
        "reason",
        "metadata",
        "created_at",
    )

    fields = readonly_fields
    list_per_page = 75

    @admin.display(
        description="Profile",
    )
    def profile_link(
        self,
        obj,
    ):
        return admin_link(
            obj.profile
        )

    @admin.display(
        description="User",
        ordering="profile__user__username",
    )
    def user_link(
        self,
        obj,
    ):
        return username_link(
            obj.profile.user
        )

    @admin.display(
        description="Actor",
        ordering="actor__username",
    )
    def actor_link(
        self,
        obj,
    ):
        return username_link(
            obj.actor
        )

    @admin.display(
        description="Reason",
    )
    def reason_preview(
        self,
        obj,
    ):
        reason = (
            obj.reason
            or ""
        ).strip()

        if not reason:
            return "-"

        if len(reason) <= 90:
            return reason

        return (
            reason[:87]
            + "..."
        )

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False