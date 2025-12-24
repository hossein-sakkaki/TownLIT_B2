# apps/sanctuary/admin.py

from datetime import timedelta

from django.contrib import admin, messages
from django.utils import timezone
from django.urls import reverse
from django.utils.html import format_html
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model
User = get_user_model()

from apps.sanctuary.services.admin_pool import sanctuary_admin_queryset
from apps.sanctuary.services.decision_engine import should_form_council, should_admin_fast_track
from apps.sanctuary.services.protection import is_edit_locked
from apps.sanctuary.services.participants import admin_set_eligibility 
from apps.sanctuary.signals.signals import (
    distribute_to_verified_members,
    finalize_sanctuary_outcome,
    notify_admins,  # ✅ use canonical assignment logic (locks + dedupe + WS + notif)
)

from .models import (
    SanctuaryRequest,
    SanctuaryReview,
    SanctuaryOutcome,
    SanctuaryProtectionLabel,
    SanctuaryParticipantProfile,
    SanctuaryParticipantAudit
)

from .forms import SanctuaryParticipantProfileAdminForm

from apps.sanctuary.constants.states import (
    PENDING,
    UNDER_REVIEW,
    RESOLVED,
    REJECTED,
    NO_OPINION,
    VIOLATION_CONFIRMED,
    VIOLATION_REJECTED,
    OUTCOME_CONFIRMED,
    OUTCOME_REJECTED,
)


# -------------------------------------------------------------------
# Small helpers
# -------------------------------------------------------------------
def _admin_change_url(obj):
    """Build admin change URL for any model instance."""
    if not obj:
        return None
    return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])


def _link(obj, label=None):
    """Clickable link to admin object."""
    if not obj:
        return "-"
    url = _admin_change_url(obj)
    if not url:
        return str(obj)
    return format_html('<a href="{}">{}</a>', url, label or str(obj))


# -------------------------------------------------------------------
# Participant Profile Admin
# -------------------------------------------------------------------

class SanctuaryParticipantAuditInline(admin.TabularInline):
    model = SanctuaryParticipantAudit
    extra = 0
    can_delete = False
    fields = ("created_at", "action", "actor", "reason")
    readonly_fields = fields
    ordering = ("-created_at",)


# Sanctuary Participant Profile -----------------------
@admin.register(SanctuaryParticipantProfile)
class SanctuaryParticipantProfileAdmin(admin.ModelAdmin):
    form = SanctuaryParticipantProfileAdminForm
    inlines = [SanctuaryParticipantAuditInline]

    list_display = (
        "id",
        "user_link",
        "is_participant",
        "is_eligible",
        "eligible_changed_at",
        "eligible_changed_by_link",
        "updated_at",
    )
    list_filter = ("is_participant", "is_eligible", "updated_at")
    search_fields = ("user__username", "user__email", "eligible_reason")
    ordering = ("-updated_at",)

    readonly_fields = (
        "participant_opted_in_at",
        "participant_opted_out_at",
        "eligible_changed_at",
        "eligible_changed_by",
        "updated_at",
    )

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Participation (User Opt-in)", {"fields": ("is_participant", "participant_opted_in_at", "participant_opted_out_at")}),
        ("Eligibility (TownLIT Gate)", {"fields": ("is_eligible", "eligible_reason", "eligible_changed_at", "eligible_changed_by")}),
        ("Config", {"fields": ("settings",)}),
        ("Meta", {"fields": ("updated_at",)}),
    )

    def user_link(self, obj):
        return _link(obj.user, f"@{obj.user.username}")
    user_link.short_description = "User"

    def eligible_changed_by_link(self, obj):
        return "-" if not obj.eligible_changed_by_id else _link(obj.eligible_changed_by, f"@{obj.eligible_changed_by.username}")
    eligible_changed_by_link.short_description = "Changed By"

    def save_model(self, request, obj, form, change):
        """
        Route eligibility changes through service to:
        - store actor
        - enforce reason
        - write audit
        - kick from open councils (hook)
        """
        if not change:
            super().save_model(request, obj, form, change)
            return

        old = SanctuaryParticipantProfile.objects.filter(pk=obj.pk).only("is_eligible").first()
        old_eligible = getattr(old, "is_eligible", True)

        new_eligible = bool(obj.is_eligible)
        reason = (obj.eligible_reason or "").strip()

        # If eligibility changed -> use service
        if old_eligible != new_eligible:
            admin_set_eligibility(
                user=obj.user,
                is_eligible=new_eligible,
                admin_user=request.user,
                reason=reason if (new_eligible is False) else None,
                metadata={"source": "admin_ui"},
            )
            self.message_user(request, "Eligibility updated via service (audit + hook applied).", level=messages.SUCCESS)

            # Refresh current object shown in admin
            obj.refresh_from_db()
            return

        # Otherwise normal save (participant toggle etc.)
        super().save_model(request, obj, form, change)

# Sanctuary Participant Audit ------------------
@admin.register(SanctuaryParticipantAudit)
class SanctuaryParticipantAuditAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "action", "actor", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("profile__user__username", "profile__user__email", "reason")
    ordering = ("-created_at",)


# -------------------------------------------------------------------
# Inline: Reviews under a request
# -------------------------------------------------------------------
class SanctuaryReviewInline(admin.TabularInline):
    model = SanctuaryReview
    extra = 0
    can_delete = False

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
    ordering = ("-reviewed_at",)


# -------------------------------------------------------------------
# SanctuaryRequest Admin
# -------------------------------------------------------------------
@admin.register(SanctuaryRequest)
class SanctuaryRequestAdmin(admin.ModelAdmin):
    """Workflow admin for Sanctuary queue + case file."""

    inlines = [SanctuaryReviewInline]

    list_display = (
        "id",
        "request_type",
        "reasons_display",
        "status",
        "resolution_mode",
        "requester_link",
        "target_link",
        "report_count_snapshot",
        "reports_count_live",
        "votes_stats",
        "assigned_admin_link",
        "created_at",
    )

    list_filter = (
        "request_type",
        "status",
        "resolution_mode",
        "created_at",
    )

    search_fields = (
        "id",
        "description",
        "requester__username",
        "assigned_admin__username",
    )

    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "updated_at",
        "content_type",
        "object_id",
        "target_link",
        "reports_count_live",
        "votes_stats",
    )

    fieldsets = (
        ("Request", {
            "fields": (
                "request_type",
                "reasons",
                "description",
                "status",
                "resolution_mode",
                "tradition_protected",
                "tradition_label",
                "report_count_snapshot",
                "created_at",
                "updated_at",
            )
        }),
        ("Actors", {
            "fields": (
                "requester",
                "assigned_admin",
                "admin_assigned_at",
            )
        }),
        ("Target (Generic)", {
            "fields": (
                "content_type",
                "object_id",
                "target_link",
                "reports_count_live",
            )
        }),
        ("Council Stats", {
            "fields": ("votes_stats",)
        }),
    )

    actions = (
        "action_assign_admin_if_needed",
        "action_reassign_admin_force",
        "action_mark_under_review",
        "action_mark_resolved",
        "action_mark_rejected",
        "action_distribute_to_council",
        "action_auto_route_by_engine",
        "action_create_outcome_confirmed_and_finalize",
        "action_create_outcome_rejected_and_finalize",
    )

    # ------------------------------------------------------------
    # Computed columns
    # ------------------------------------------------------------
    def requester_link(self, obj):
        return _link(obj.requester, f"@{obj.requester.username}")
    requester_link.short_description = "Requester"

    def assigned_admin_link(self, obj):
        if not obj.assigned_admin_id:
            return "-"
        return _link(obj.assigned_admin, f"@{obj.assigned_admin.username}")
    assigned_admin_link.short_description = "Assigned Admin"

    def reasons_display(self, obj):
        # reasons is a JSON list of codes
        rs = getattr(obj, "reasons", None) or []
        if not isinstance(rs, list):
            return "-"
        return ", ".join([str(x) for x in rs[:6]]) + (" …" if len(rs) > 6 else "")
    reasons_display.short_description = "Reasons"

    def target_link(self, obj):
        target = getattr(obj, "content_object", None)
        if not target:
            return "-"
        locked = is_edit_locked(target)
        badge = " 🔒" if locked else ""
        return format_html("{}{}", _link(target), badge)
    target_link.short_description = "Target"

    def reports_count_live(self, obj):
        target = getattr(obj, "content_object", None)
        if not target:
            return "-"
        cnt = getattr(target, "reports_count", None)
        return "n/a" if cnt is None else str(cnt)
    reports_count_live.short_description = "Reports (live)"

    def votes_stats(self, obj):
        qs = obj.reviews.all()

        # Prefer active slots (replacement flow)
        if any(f.name == "is_active" for f in SanctuaryReview._meta.get_fields()):
            qs = qs.filter(is_active=True)

        plus = qs.filter(review_status=VIOLATION_CONFIRMED).count()
        minus = qs.filter(review_status=VIOLATION_REJECTED).count()
        zero = qs.filter(review_status=NO_OPINION).count()
        return f"+{plus} / -{minus} / 0:{zero}"
    votes_stats.short_description = "Votes"

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------
    @admin.action(description="Assign admin (canonical, if needed)")
    def action_assign_admin_if_needed(self, request, queryset):
        ok = 0
        for sr in queryset:
            assigned = notify_admins(sr, force=False)
            if assigned:
                ok += 1
        self.message_user(request, f"Processed admin assignment for {ok} request(s).")

    @admin.action(description="Reassign admin (canonical, force)")
    def action_reassign_admin_force(self, request, queryset):
        ok = 0
        for sr in queryset:
            assigned = notify_admins(sr, force=True)
            if assigned:
                ok += 1
        self.message_user(request, f"Forced reassign for {ok} request(s).")

    @admin.action(description="Mark UNDER_REVIEW")
    def action_mark_under_review(self, request, queryset):
        queryset.update(status=UNDER_REVIEW)

    @admin.action(description="Mark RESOLVED")
    def action_mark_resolved(self, request, queryset):
        queryset.update(status=RESOLVED)

    @admin.action(description="Mark REJECTED")
    def action_mark_rejected(self, request, queryset):
        queryset.update(status=REJECTED)

    @admin.action(description="Distribute to council (12 members)")
    def action_distribute_to_council(self, request, queryset):
        ok = 0
        for sr in queryset:
            try:
                distribute_to_verified_members(sr)  # sets status+mode internally
                ok += 1
            except Exception:
                pass
        self.message_user(request, f"Council distribution triggered for {ok} request(s).")

    @admin.action(description="Auto-route by decision_engine (uses snapshot)")
    def action_auto_route_by_engine(self, request, queryset):
        fast = 0
        council = 0
        monitor = 0

        for sr in queryset:
            report_count = int(getattr(sr, "report_count_snapshot", 1) or 1)

            if should_admin_fast_track(sr.request_type, report_count):
                notify_admins(sr, force=False)
                fast += 1
                continue

            if should_form_council(sr.request_type, report_count):
                try:
                    distribute_to_verified_members(sr)
                    council += 1
                except Exception:
                    pass
                continue

            monitor += 1

        self.message_user(request, f"Auto-route → fast={fast}, council={council}, monitor={monitor}")

    def _create_outcome(self, sr: SanctuaryRequest, outcome_status: str):
        # Avoid duplicates (admin can click twice)
        if sr.outcomes.filter(outcome_status__in=[OUTCOME_CONFIRMED, OUTCOME_REJECTED]).exists():
            return None

        out = SanctuaryOutcome.objects.create(
            outcome_status=outcome_status,
            content_type=sr.content_type,
            object_id=sr.object_id,
            appeal_deadline=timezone.now() + timedelta(days=7),
        )
        out.sanctuary_requests.add(sr)
        return out

    @admin.action(description="Create OUTCOME: Confirmed + Finalize")
    def action_create_outcome_confirmed_and_finalize(self, request, queryset):
        ok = 0
        for sr in queryset:
            out = self._create_outcome(sr, OUTCOME_CONFIRMED)
            if not out:
                continue
            finalize_sanctuary_outcome(out)
            ok += 1
        self.message_user(request, f"Confirmed + finalized {ok} outcome(s).")

    @admin.action(description="Create OUTCOME: Rejected + Finalize")
    def action_create_outcome_rejected_and_finalize(self, request, queryset):
        ok = 0
        for sr in queryset:
            out = self._create_outcome(sr, OUTCOME_REJECTED)
            if not out:
                continue
            finalize_sanctuary_outcome(out)
            ok += 1
        self.message_user(request, f"Rejected + finalized {ok} outcome(s).")


# -------------------------------------------------------------------
# SanctuaryOutcome Admin
# -------------------------------------------------------------------
@admin.register(SanctuaryOutcome)
class SanctuaryOutcomeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "outcome_status",
        "target_link",
        "requests_count",
        "is_appealed",
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
    search_fields = ("id", "appeal_message", "assigned_admin__username")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    readonly_fields = (
        "created_at",
        "finalized_at",
        "content_type",
        "object_id",
        "target_link",
        "requests_count",
    )

    fieldsets = (
        ("Outcome", {"fields": ("outcome_status", "created_at", "finalized_at", "sanctuary_requests")}),
        ("Target (Generic)", {"fields": ("content_type", "object_id", "target_link", "requests_count")}),
        ("Appeal", {"fields": ("is_appealed", "appeal_message", "appeal_deadline", "admin_reviewed", "assigned_admin", "admin_assigned_at")}),
    )

    actions = (
        "action_finalize_outcome",
        "action_reassign_appeal_admin",
        "action_extend_appeal_deadline_7d",
    )

    def target_link(self, obj):
        target = getattr(obj, "content_object", None)
        if not target:
            return "-"
        locked = is_edit_locked(target)
        badge = " 🔒" if locked else ""
        return format_html("{}{}", _link(target), badge)
    target_link.short_description = "Target"

    def requests_count(self, obj):
        return obj.sanctuary_requests.count()
    requests_count.short_description = "Requests"

    def assigned_admin_link(self, obj):
        if not obj.assigned_admin_id:
            return "-"
        return _link(obj.assigned_admin, f"@{obj.assigned_admin.username}")
    assigned_admin_link.short_description = "Appeal Admin"

    @admin.action(description="Finalize outcomes (finalize_sanctuary_outcome)")
    def action_finalize_outcome(self, request, queryset):
        ok = 0
        for out in queryset:
            try:
                finalize_sanctuary_outcome(out)
                ok += 1
            except Exception:
                pass
        self.message_user(request, f"Finalized {ok} outcome(s).")

    @admin.action(description="Reassign appeal admin (random)")
    def action_reassign_appeal_admin(self, request, queryset):
        admins = sanctuary_admin_queryset()
        ok = 0
        for out in queryset:
            current_id = out.assigned_admin_id
            pick = admins.exclude(id=current_id).order_by("?").first()
            if pick:
                out.assigned_admin = pick
                out.admin_assigned_at = timezone.now()
                out.save(update_fields=["assigned_admin", "admin_assigned_at"])
                ok += 1
        self.message_user(request, f"Reassigned appeal admin for {ok} outcome(s).")

    @admin.action(description="Extend appeal deadline +7 days")
    def action_extend_appeal_deadline_7d(self, request, queryset):
        ok = 0
        now = timezone.now()
        for out in queryset:
            out.appeal_deadline = (out.appeal_deadline or now) + timedelta(days=7)
            out.save(update_fields=["appeal_deadline"])
            ok += 1
        self.message_user(request, f"Extended deadline for {ok} outcome(s).")


# -------------------------------------------------------------------
# SanctuaryReview Admin
# -------------------------------------------------------------------
@admin.register(SanctuaryReview)
class SanctuaryReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "sanctuary_request", "reviewer_link", "review_status", "reviewed_at", "assigned_at", "is_active")
    list_filter = ("review_status", "is_active", "reviewed_at")
    search_fields = ("id", "reviewer__username", "sanctuary_request__id")
    ordering = ("-reviewed_at",)
    readonly_fields = ("reviewed_at", "assigned_at")

    def reviewer_link(self, obj):
        return _link(obj.reviewer, f"@{obj.reviewer.username}")
    reviewer_link.short_description = "Reviewer"


# -------------------------------------------------------------------
# Protection Labels Admin
# -------------------------------------------------------------------
@admin.register(SanctuaryProtectionLabel)
class SanctuaryProtectionLabelAdmin(admin.ModelAdmin):
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
    list_filter = ("label_type", "is_active", "applied_by")
    search_fields = ("id", "label_type", "note")
    ordering = ("-applied_at",)

    readonly_fields = ("applied_at",)

    fieldsets = (
        ("Label", {"fields": ("label_type", "is_active", "applied_by", "note")}),
        ("Target (Generic)", {"fields": ("content_type", "object_id")}),
        ("Audit", {"fields": ("outcome", "created_by", "applied_at", "expires_at")}),
    )

    actions = (
        "action_activate",
        "action_deactivate",
        "action_extend_90_days",
        "action_deactivate_if_expired",
    )

    def target_link(self, obj):
        target = getattr(obj, "content_object", None)
        return "-" if not target else _link(target)
    target_link.short_description = "Target"

    def created_by_link(self, obj):
        return "-" if not obj.created_by_id else _link(obj.created_by, f"@{obj.created_by.username}")
    created_by_link.short_description = "Created By"

    def outcome_link(self, obj):
        return "-" if not obj.outcome_id else _link(obj.outcome, f"Outcome #{obj.outcome_id}")
    outcome_link.short_description = "Outcome"

    @admin.action(description="Activate selected labels")
    def action_activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected labels")
    def action_deactivate(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Extend expiry +90 days")
    def action_extend_90_days(self, request, queryset):
        now = timezone.now()
        ok = 0
        for lbl in queryset:
            if lbl.expires_at and lbl.expires_at > now:
                lbl.expires_at = lbl.expires_at + timedelta(days=90)
            else:
                lbl.expires_at = now + timedelta(days=90)
            lbl.is_active = True
            lbl.save(update_fields=["expires_at", "is_active"])
            ok += 1
        self.message_user(request, f"Extended {ok} label(s) by 90 days.")

    @admin.action(description="Deactivate expired labels (safe)")
    def action_deactivate_if_expired(self, request, queryset):
        now = timezone.now()
        qs = queryset.filter(is_active=True).filter(expires_at__isnull=False, expires_at__lte=now)
        count = qs.update(is_active=False)
        self.message_user(request, f"Deactivated {count} expired label(s).")
