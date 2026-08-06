# apps/sanctuary/admin/requests.py

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from django.utils.html import format_html

from apps.sanctuary.constants.states import (
    NO_OPINION,
    OUTCOME_CONFIRMED,
    OUTCOME_REJECTED,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
)
from apps.sanctuary.models import (
    SanctuaryOutcome,
    SanctuaryRequest,
    SanctuaryReview,
)
from apps.sanctuary.services.counter_resolver import (
    resolve_active_report_count,
)
from apps.sanctuary.services.decision_engine import (
    should_admin_fast_track,
    should_form_council,
)
from apps.sanctuary.services.protection import (
    is_edit_locked,
)
from apps.sanctuary.services.safety_hold import (
    apply_sanctuary_safety_hold,
)
from apps.sanctuary.services.severe_counter import (
    resolve_active_severe_request_count,
)
from apps.sanctuary.signals.signals import (
    distribute_to_verified_members,
    finalize_sanctuary_outcome,
    notify_admins,
)

from .helpers import (
    AdminActionResult,
    admin_link,
    report_admin_action_summary,
    target_link_with_lock,
    username_link,
)
from .media_preview import (
    sanctuary_admin_media_panel,
)

class SanctuaryReviewInline(
    admin.TabularInline
):
    model = SanctuaryReview
    extra = 0
    can_delete = False
    show_change_link = True

    fields = (
        "reviewer",
        "review_status",
        "comment",
        "reviewed_at",
        "assigned_at",
        "is_active",
        "is_primary_tradition_match",
    )

    readonly_fields = fields

    ordering = (
        "-is_active",
        "-reviewed_at",
        "-assigned_at",
        "-id",
    )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(
    SanctuaryRequest
)
class SanctuaryRequestAdmin(
    admin.ModelAdmin
):
    """
    Operational Sanctuary queue.

    Workflow transitions are intentionally exposed only through
    canonical services/actions where such services exist.
    """

    inlines = [
        SanctuaryReviewInline
    ]

    list_display = (
        "id",
        "priority_badge",
        "request_type",
        "reasons_display",
        "status",
        "resolution_mode",
        "requester_link",
        "target_link",
        "active_reports_count",
        "active_severe_count",
        "votes_stats",
        "assigned_admin_link",
        "created_at",
    )

    list_filter = (
        "request_type",
        "status",
        "resolution_mode",
        "tradition_protected",
        "created_at",
    )

    search_fields = (
        "=id",
        "description",
        "requester__username",
        "requester__email",
        "assigned_admin__username",
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
        "requester",
        "assigned_admin",
        "content_type",
    )

    list_per_page = 50
    save_on_top = True

    readonly_fields = (
        "request_type",
        "reasons",
        "description",
        "status",
        "resolution_mode",
        "tradition_protected",
        "tradition_label",
        "report_count_snapshot",
        "requester",
        "assigned_admin",
        "admin_assigned_at",
        "created_at",
        "updated_at",
        "content_type",
        "object_id",
        "target_link",
        "target_media_preview",
        "active_reports_count",
        "active_severe_count",
        "votes_stats",
    )

    fieldsets = (
        (
            "Case summary",
            {
                "fields": (
                    "request_type",
                    "status",
                    "resolution_mode",
                    "reasons",
                    "description",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
        (
            "Requester and assignment",
            {
                "fields": (
                    "requester",
                    "assigned_admin",
                    "admin_assigned_at",
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
                    "report_count_snapshot",
                    "active_reports_count",
                    "active_severe_count",
                ),
            },
        ),
        (
            "Council",
            {
                "fields": (
                    "votes_stats",
                ),
            },
        ),
        (
            "Tradition protection",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "tradition_protected",
                    "tradition_label",
                ),
            },
        ),
    )

    actions = (
        "action_assign_admin_if_needed",
        "action_reassign_admin_force",
        "action_distribute_to_council",
        "action_auto_route_by_engine",
        (
            "action_create_outcome_"
            "confirmed_and_finalize"
        ),
        (
            "action_create_outcome_"
            "rejected_and_finalize"
        ),
    )

    def get_queryset(
        self,
        request,
    ):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "requester",
                "assigned_admin",
                "content_type",
            )
            .prefetch_related(
                "reviews",
                "outcomes",
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
            return format_html(
                '<span style="color:#b42318;">'
                "Target unavailable"
                "</span>"
            )

        return sanctuary_admin_media_panel(
            target
        )

    @admin.display(
        description="Requester",
        ordering="requester__username",
    )
    def requester_link(
        self,
        obj,
    ):
        return username_link(
            obj.requester
        )

    @admin.display(
        description="Assigned admin",
        ordering="assigned_admin__username",
    )
    def assigned_admin_link(
        self,
        obj,
    ):
        return username_link(
            obj.assigned_admin
        )

    @admin.display(
        description="Reasons",
    )
    def reasons_display(
        self,
        obj,
    ):
        reasons = (
            getattr(
                obj,
                "reasons",
                None,
            )
            or []
        )

        if not isinstance(
            reasons,
            list,
        ):
            return "-"

        rendered = ", ".join(
            str(reason)
            for reason in reasons[:5]
        )

        if len(reasons) > 5:
            rendered += " …"

        return (
            rendered
            or "-"
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
            return format_html(
                '<span style="color:#b42318;">'
                "Target unavailable"
                "</span>"
            )

        return target_link_with_lock(
            target,
            is_locked=is_edit_locked(
                target
            ),
        )

    def _active_report_count(
        self,
        obj,
    ) -> int:
        return resolve_active_report_count(
            request_type=obj.request_type,
            content_type=obj.content_type,
            object_id=obj.object_id,
        )

    def _active_severe_count(
        self,
        obj,
    ) -> int:
        return (
            resolve_active_severe_request_count(
                request_type=(
                    obj.request_type
                ),
                content_type=(
                    obj.content_type
                ),
                object_id=obj.object_id,
            )
        )

    @admin.display(
        description="Active reports",
    )
    def active_reports_count(
        self,
        obj,
    ):
        try:
            return self._active_report_count(
                obj
            )
        except Exception:
            return "Error"

    @admin.display(
        description="Severe reports",
    )
    def active_severe_count(
        self,
        obj,
    ):
        try:
            return self._active_severe_count(
                obj
            )
        except Exception:
            return "Error"

    @admin.display(
        description="Priority",
    )
    def priority_badge(
        self,
        obj,
    ):
        try:
            severe_count = (
                self._active_severe_count(
                    obj
                )
            )

            fast_track = (
                should_admin_fast_track(
                    target_type=(
                        obj.request_type
                    ),
                    reasons=(
                        obj.reasons
                    ),
                    severe_request_count=(
                        severe_count
                    ),
                )
            )

            if fast_track:
                return format_html(
                    '<strong style="color:#b42318;">'
                    "URGENT"
                    "</strong>"
                )

            active_count = (
                self._active_report_count(
                    obj
                )
            )

            if should_form_council(
                obj.request_type,
                active_count,
            ):
                return format_html(
                    '<strong style="color:#9a6700;">'
                    "COUNCIL"
                    "</strong>"
                )

            return format_html(
                '<span style="color:#667085;">'
                "MONITOR"
                "</span>"
            )

        except Exception:
            return "Unknown"

    @admin.display(
        description="Votes",
    )
    def votes_stats(
        self,
        obj,
    ):
        reviews = obj.reviews.all()

        if any(
            field.name == "is_active"
            for field in (
                SanctuaryReview
                ._meta
                .get_fields()
            )
        ):
            reviews = reviews.filter(
                is_active=True
            )

        confirmed = reviews.filter(
            review_status=(
                VIOLATION_CONFIRMED
            )
        ).count()

        rejected = reviews.filter(
            review_status=(
                VIOLATION_REJECTED
            )
        ).count()

        pending = reviews.filter(
            review_status=NO_OPINION
        ).count()

        return (
            f"Confirmed {confirmed} · "
            f"Rejected {rejected} · "
            f"Pending {pending}"
        )

    @admin.action(
        description=(
            "Assign an admin using the "
            "canonical assignment service"
        )
    )
    def action_assign_admin_if_needed(
        self,
        request,
        queryset,
    ):
        result = AdminActionResult()

        for sanctuary_request in queryset:
            try:
                assigned = notify_admins(
                    sanctuary_request,
                    force=False,
                )

                if assigned:
                    result.mark_succeeded()
                else:
                    result.mark_skipped()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Request "
                        f"{sanctuary_request.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Admin assignment",
            result=result,
        )

    @admin.action(
        description=(
            "Force reassignment using the "
            "canonical assignment service"
        )
    )
    def action_reassign_admin_force(
        self,
        request,
        queryset,
    ):
        result = AdminActionResult()

        for sanctuary_request in queryset:
            try:
                assigned = notify_admins(
                    sanctuary_request,
                    force=True,
                )

                if assigned:
                    result.mark_succeeded()
                else:
                    result.mark_skipped()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Request "
                        f"{sanctuary_request.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Forced reassignment",
            result=result,
        )

    @admin.action(
        description=(
            "Distribute eligible requests "
            "to a Sanctuary council"
        )
    )
    def action_distribute_to_council(
        self,
        request,
        queryset,
    ):
        result = AdminActionResult()

        for sanctuary_request in queryset:
            try:
                distribute_to_verified_members(
                    sanctuary_request
                )

                result.mark_succeeded()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Request "
                        f"{sanctuary_request.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label="Council distribution",
            result=result,
        )

    @admin.action(
        description=(
            "Auto-route using the current "
            "Sanctuary decision engine"
        )
    )
    def action_auto_route_by_engine(
        self,
        request,
        queryset,
    ):
        fast_track_count = 0
        council_count = 0
        monitor_count = 0
        failed_count = 0

        for sanctuary_request in (
            queryset.select_related(
                "content_type"
            )
        ):
            try:
                active_count = (
                    self._active_report_count(
                        sanctuary_request
                    )
                )

                severe_count = (
                    self._active_severe_count(
                        sanctuary_request
                    )
                )

                if should_admin_fast_track(
                    target_type=(
                        sanctuary_request
                        .request_type
                    ),
                    reasons=(
                        sanctuary_request
                        .reasons
                    ),
                    severe_request_count=(
                        severe_count
                    ),
                ):
                    notify_admins(
                        sanctuary_request,
                        force=False,
                    )

                    apply_sanctuary_safety_hold(
                        sanctuary_request
                    )

                    fast_track_count += 1
                    continue

                if should_form_council(
                    sanctuary_request
                    .request_type,
                    active_count,
                ):
                    distribute_to_verified_members(
                        sanctuary_request
                    )

                    council_count += 1
                    continue

                monitor_count += 1

            except Exception as error:
                failed_count += 1

                self.message_user(
                    request,
                    (
                        f"Request "
                        f"{sanctuary_request.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        level = (
            messages.WARNING
            if failed_count
            else messages.SUCCESS
        )

        self.message_user(
            request,
            (
                "Auto-route completed: "
                f"{fast_track_count} admin "
                "fast-track, "
                f"{council_count} council, "
                f"{monitor_count} monitor, "
                f"{failed_count} failed."
            ),
            level=level,
        )

    def _create_outcome(
        self,
        *,
        sanctuary_request,
        outcome_status,
        actor,
    ):
        with transaction.atomic():
            locked_request = (
                SanctuaryRequest
                .objects
                .select_for_update()
                .select_related(
                    "content_type"
                )
                .get(
                    pk=(
                        sanctuary_request.pk
                    )
                )
            )

            existing_outcome = (
                locked_request
                .outcomes
                .filter(
                    outcome_status__in=[
                        OUTCOME_CONFIRMED,
                        OUTCOME_REJECTED,
                    ]
                )
                .first()
            )

            if existing_outcome:
                return None

            outcome = (
                SanctuaryOutcome
                .objects
                .create(
                    outcome_status=(
                        outcome_status
                    ),
                    content_type=(
                        locked_request
                        .content_type
                    ),
                    object_id=(
                        locked_request
                        .object_id
                    ),
                    appeal_deadline=(
                        timezone.now()
                        + timedelta(days=7)
                    ),
                    assigned_admin=actor,
                    admin_assigned_at=(
                        timezone.now()
                    ),
                )
            )

            outcome.sanctuary_requests.add(
                locked_request
            )

            return outcome

    def _create_and_finalize(
        self,
        *,
        request,
        queryset,
        outcome_status,
        label,
    ):
        result = AdminActionResult()

        for sanctuary_request in queryset:
            try:
                outcome = self._create_outcome(
                    sanctuary_request=(
                        sanctuary_request
                    ),
                    outcome_status=(
                        outcome_status
                    ),
                    actor=request.user,
                )

                if outcome is None:
                    result.mark_skipped()
                    continue

                finalize_sanctuary_outcome(
                    outcome
                )

                result.mark_succeeded()

            except Exception as error:
                result.mark_failed()

                self.message_user(
                    request,
                    (
                        f"Request "
                        f"{sanctuary_request.pk}: "
                        f"{error}"
                    ),
                    level=messages.ERROR,
                )

        report_admin_action_summary(
            model_admin=self,
            request=request,
            label=label,
            result=result,
        )

    @admin.action(
        description=(
            "Create confirmed outcome "
            "and finalize"
        )
    )
    def action_create_outcome_confirmed_and_finalize(
        self,
        request,
        queryset,
    ):
        self._create_and_finalize(
            request=request,
            queryset=queryset,
            outcome_status=(
                OUTCOME_CONFIRMED
            ),
            label=(
                "Confirmed outcome finalization"
            ),
        )

    @admin.action(
        description=(
            "Create rejected outcome "
            "and finalize"
        )
    )
    def action_create_outcome_rejected_and_finalize(
        self,
        request,
        queryset,
    ):
        self._create_and_finalize(
            request=request,
            queryset=queryset,
            outcome_status=(
                OUTCOME_REJECTED
            ),
            label=(
                "Rejected outcome finalization"
            ),
        )

    def has_add_permission(
        self,
        request,
    ):
        # Requests must come through the app/API.
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        # Preserve the case history.
        return False