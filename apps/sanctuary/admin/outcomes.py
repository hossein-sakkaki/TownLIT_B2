# apps/sanctuary/admin/outcomes.py

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from apps.sanctuary.models import (
    SanctuaryOutcome,
)
from apps.sanctuary.services.admin_pool import (
    sanctuary_admin_queryset,
)
from apps.sanctuary.services.protection import (
    is_edit_locked,
)
from apps.sanctuary.signals.signals import (
    finalize_sanctuary_outcome,
)
from .media_preview import (
    sanctuary_admin_media_panel,
)

from .helpers import (
    AdminActionResult,
    admin_link,
    report_admin_action_summary,
    target_link_with_lock,
    username_link,
)


@admin.register(
    SanctuaryOutcome
)
class SanctuaryOutcomeAdmin(
    admin.ModelAdmin
):
    list_display = (
        "id",
        "outcome_status",
        "target_link",
        "requests_count",
        "is_appealed",
        "appeal_deadline",
        "admin_reviewed",
        "assigned_admin_link",
        "created_at",
        "finalized_at",
    )

    list_filter = (
        "outcome_status",
        "is_appealed",
        "admin_reviewed",
        "created_at",
        "finalized_at",
    )

    search_fields = (
        "=id",
        "appeal_message",
        "assigned_admin__username",
        "assigned_admin__email",
        "object_id",
    )

    date_hierarchy = (
        "created_at"
    )

    ordering = (
        "-created_at",
        "-id",
    )

    list_select_related = (
        "assigned_admin",
        "content_type",
    )

    filter_horizontal = (
        "sanctuary_requests",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "outcome_status",
        "created_at",
        "finalized_at",
        "content_type",
        "object_id",
        "target_link",
        "target_media_preview",
        "requests_count",
        "sanctuary_requests",
        "is_appealed",
        "appeal_message",
    )

    fieldsets = (
        (
            "Outcome",
            {
                "fields": (
                    "outcome_status",
                    "created_at",
                    "finalized_at",
                    "sanctuary_requests",
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
                    "requests_count",
                ),
            },
        ),
        (
            "Appeal",
            {
                "fields": (
                    "is_appealed",
                    "appeal_message",
                    "appeal_deadline",
                    "admin_reviewed",
                    "assigned_admin",
                    "admin_assigned_at",
                ),
            },
        ),
    )

    actions = (
        "action_finalize_outcome",
        "action_reassign_appeal_admin",
        "action_extend_appeal_deadline_7d",
        "action_mark_appeal_admin_reviewed",
    )

    def get_queryset(
        self,
        request,
    ):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "assigned_admin",
                "content_type",
            )
            .prefetch_related(
                "sanctuary_requests"
            )
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

        if target is None:
            return "Target unavailable"

        return target_link_with_lock(
            target,
            is_locked=is_edit_locked(
                target
            ),
        )

    @admin.display(
        description="Requests",
    )
    def requests_count(
        self,
        obj,
    ):
        return (
            obj.sanctuary_requests.count()
        )

    @admin.display(
        description="Appeal admin",
        ordering="assigned_admin__username",
    )
    def assigned_admin_link(
        self,
        obj,
    ):
        return username_link(
            obj.assigned_admin
        )

    @admin.action(
        description=(
            "Finalize selected outcomes "
            "using the canonical service"
        )
    )
    def action_finalize_outcome(
        self,
        request,
        queryset,
    ):
        result = AdminActionResult()

        for outcome in queryset:
            try:
                finalize_sanctuary_outcome(
                    outcome
                )

                result.mark_succeeded()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Outcome "
                        f"{outcome.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Outcome finalization",
            result=result,
        )

    @admin.action(
        description=(
            "Assign another Sanctuary "
            "admin to selected appeals"
        )
    )
    def action_reassign_appeal_admin(
        self,
        request,
        queryset,
    ):
        admins = (
            sanctuary_admin_queryset()
        )

        result = AdminActionResult()

        for outcome in queryset:
            if not outcome.is_appealed:
                result.mark_skipped()
                continue

            try:
                with transaction.atomic():
                    locked_outcome = (
                        SanctuaryOutcome
                        .objects
                        .select_for_update()
                        .get(
                            pk=outcome.pk
                        )
                    )

                    candidate = (
                        admins
                        .exclude(
                            id=(
                                locked_outcome
                                .assigned_admin_id
                            )
                        )
                        .order_by("?")
                        .first()
                    )

                    if candidate is None:
                        result.mark_skipped()
                        continue

                    locked_outcome.assigned_admin = (
                        candidate
                    )

                    locked_outcome.admin_assigned_at = (
                        timezone.now()
                    )

                    locked_outcome.save(
                        update_fields=[
                            "assigned_admin",
                            "admin_assigned_at",
                        ]
                    )

                result.mark_succeeded()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Outcome "
                        f"{outcome.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Appeal reassignment",
            result=result,
        )

    @admin.action(
        description=(
            "Extend appeal deadline "
            "by seven days"
        )
    )
    def action_extend_appeal_deadline_7d(
        self,
        request,
        queryset,
    ):
        result = AdminActionResult()
        now = timezone.now()

        for outcome in queryset:
            if not outcome.is_appealed:
                result.mark_skipped()
                continue

            try:
                baseline = (
                    outcome.appeal_deadline
                    if (
                        outcome.appeal_deadline
                        and (
                            outcome
                            .appeal_deadline
                            > now
                        )
                    )
                    else now
                )

                outcome.appeal_deadline = (
                    baseline
                    + timedelta(days=7)
                )

                outcome.save(
                    update_fields=[
                        "appeal_deadline"
                    ]
                )

                result.mark_succeeded()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Outcome "
                        f"{outcome.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Appeal deadline extension",
            result=result,
        )

    @admin.action(
        description=(
            "Mark selected appealed outcomes "
            "as admin reviewed"
        )
    )
    def action_mark_appeal_admin_reviewed(
        self,
        request,
        queryset,
    ):
        count = (
            queryset
            .filter(
                is_appealed=True,
            )
            .update(
                admin_reviewed=True
            )
        )

        self.message_user(
            request,
            (
                f"{count} appealed outcome(s) "
                "marked as reviewed."
            ),
            level=messages.SUCCESS,
        )

    def has_add_permission(
        self,
        request,
    ):
        # Outcomes should originate from canonical workflow actions.
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False