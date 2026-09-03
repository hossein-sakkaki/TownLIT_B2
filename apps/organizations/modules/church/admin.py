# apps/organizations/modules/church/admin.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.contrib import admin

from apps.organizations.modules.church.models import (
    ChurchAttendanceRecord,
    ChurchAttendanceSession,
    ChurchAuditLog,
    ChurchCampus,
    ChurchGatheringOccurrence,
    ChurchGatheringSeries,
    ChurchLeadershipAssignment,
    ChurchMinistry,
    ChurchMinistryMembership,
    ChurchWorkspace,
    ChurchServingTeam,
    ChurchServingTeamMembership,
    ChurchServicePlan,
    ChurchServicePlanItem,
    ChurchServingAssignment,
    ChurchResource,
    ChurchResourceReservation,
    ChurchCongregant,
    ChurchHousehold,
    ChurchHouseholdMembership,
    ChurchTeachingSeries,
)

from apps.posts.models.church_teaching import (
    ChurchTeachingContent,
    ChurchTeachingScriptureReference,
)


@admin.register(ChurchWorkspace)
class ChurchWorkspaceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization_name",
        "attendance_tracking_enabled",
        "membership_directory_enabled",
        "updated_at",
    )
    search_fields = ("activation__organization__name",)

    @admin.display(description="Organization")
    def organization_name(self, obj):
        return obj.activation.organization.name


@admin.register(ChurchCampus)
class ChurchCampusAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "status",
        "is_primary",
        "sort_order",
    )
    list_filter = ("status", "is_primary")
    search_fields = ("name", "slug", "workspace__activation__organization__name")


@admin.register(ChurchMinistry)
class ChurchMinistryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "campus",
        "status",
        "visibility",
    )
    list_filter = ("status", "visibility")
    search_fields = ("name", "slug", "workspace__activation__organization__name")


@admin.register(ChurchMinistryMembership)
class ChurchMinistryMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "ministry",
        "membership",
        "participation_role",
        "status",
        "joined_at",
    )
    list_filter = ("status", "participation_role")


@admin.register(ChurchLeadershipAssignment)
class ChurchLeadershipAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "effective_title",
        "workspace",
        "membership",
        "campus",
        "ministry",
        "status",
        "publicly_listed",
    )
    list_filter = ("status", "position_type", "publicly_listed")


@admin.register(ChurchGatheringSeries)
class ChurchGatheringSeriesAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "gathering_type",
        "recurrence_frequency",
        "weekday",
        "status",
    )
    list_filter = ("status", "gathering_type", "recurrence_frequency")


@admin.register(ChurchGatheringOccurrence)
class ChurchGatheringOccurrenceAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "workspace",
        "starts_at",
        "ends_at",
        "status",
        "source",
    )
    list_filter = ("status", "source", "gathering_type")
    date_hierarchy = "starts_at"


@admin.register(ChurchAttendanceSession)
class ChurchAttendanceSessionAdmin(admin.ModelAdmin):
    list_display = (
        "occurrence",
        "workspace",
        "status",
        "opened_at",
        "closed_at",
        "total_attendance_count",
    )
    list_filter = ("status",)


@admin.register(ChurchAttendanceRecord)
class ChurchAttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "session",
        "membership",
        "presence",
        "source",
        "checked_in_at",
        "checked_out_at",
    )
    list_filter = ("presence", "source")


@admin.register(ChurchAuditLog)
class ChurchAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "workspace",
        "event",
        "actor",
        "entity_type",
        "entity_public_id",
        "created_at",
    )
    list_filter = ("event", "entity_type")
    readonly_fields = (
        "workspace",
        "event",
        "actor",
        "membership",
        "entity_type",
        "entity_public_id",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChurchServingTeam)
class ChurchServingTeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "campus",
        "ministry",
        "status",
        "sort_order",
    )
    list_filter = ("status",)
    search_fields = ("name", "slug", "workspace__activation__organization__name")


@admin.register(ChurchServingTeamMembership)
class ChurchServingTeamMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "team",
        "membership",
        "role_title",
        "is_team_lead",
        "status",
        "joined_at",
    )
    list_filter = ("status", "is_team_lead", "is_publicly_listed")


@admin.register(ChurchServicePlan)
class ChurchServicePlanAdmin(admin.ModelAdmin):
    list_display = (
        "occurrence",
        "workspace",
        "status",
        "theme",
        "published_at",
        "completed_at",
    )
    list_filter = ("status",)
    search_fields = ("theme", "occurrence__title", "workspace__activation__organization__name")


@admin.register(ChurchServicePlanItem)
class ChurchServicePlanItemAdmin(admin.ModelAdmin):
    list_display = (
        "service_plan",
        "sort_order",
        "item_type",
        "title",
        "serving_team",
        "planned_duration_seconds",
    )
    list_filter = ("item_type", "is_optional", "is_internal_only")
    search_fields = ("title", "service_plan__occurrence__title")


@admin.register(ChurchServingAssignment)
class ChurchServingAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        "service_plan",
        "membership",
        "team",
        "role_label",
        "status",
        "checked_in_at",
        "checked_out_at",
    )
    list_filter = ("status",)
    search_fields = ("role_label", "membership__member__user__email")


@admin.register(ChurchResource)
class ChurchResourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "resource_type",
        "campus",
        "status",
        "quantity_available",
        "is_reservable",
    )
    list_filter = ("resource_type", "status", "is_reservable")
    search_fields = ("name", "slug", "workspace__activation__organization__name")


@admin.register(ChurchResourceReservation)
class ChurchResourceReservationAdmin(admin.ModelAdmin):
    list_display = (
        "resource",
        "occurrence",
        "quantity",
        "starts_at",
        "ends_at",
        "status",
    )
    list_filter = ("status", "resource__resource_type")
    date_hierarchy = "starts_at"


@admin.register(ChurchCongregant)
class ChurchCongregantAdmin(admin.ModelAdmin):
    list_display = (
        "display_name_snapshot",
        "workspace",
        "status",
        "campus",
        "directory_visibility",
        "is_active",
    )
    list_filter = ("status", "directory_visibility", "is_active")
    search_fields = (
        "display_name_snapshot",
        "member__user__username",
        "guest_profile__user__username",
        "workspace__activation__organization__name",
    )


@admin.register(ChurchHousehold)
class ChurchHouseholdAdmin(admin.ModelAdmin):
    list_display = ("name", "workspace", "campus", "status", "updated_at")
    list_filter = ("status",)
    search_fields = ("name", "workspace__activation__organization__name")


@admin.register(ChurchHouseholdMembership)
class ChurchHouseholdMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "household",
        "congregant",
        "relationship_type",
        "is_primary",
        "status",
        "joined_at",
    )
    list_filter = ("status", "relationship_type", "is_primary")


# Pastoral care models are intentionally not registered in the generic Django admin.
# Their confidential content requires the explicit Church pastoral access policy.


@admin.register(ChurchTeachingSeries)
class ChurchTeachingSeriesAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "workspace",
        "campus",
        "ministry",
        "status",
        "sort_order",
    )
    list_filter = ("status",)
    search_fields = (
        "name",
        "slug",
        "workspace__activation__organization__name",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class _ReadOnlyChurchTeachingAdmin(admin.ModelAdmin):
    """Keep Content Safety and lifecycle writes inside domain services."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChurchTeachingContent)
class ChurchTeachingContentAdmin(_ReadOnlyChurchTeachingAdmin):
    list_display = (
        "title",
        "workspace",
        "teaching_type",
        "content_format",
        "status",
        "audience",
        "is_converted",
        "published_at",
    )
    list_filter = (
        "status",
        "audience",
        "teaching_type",
        "content_format",
        "is_converted",
        "is_suspended",
        "is_active",
    )
    search_fields = (
        "title",
        "speaker_name_snapshot",
        "workspace__activation__organization__name",
    )
    readonly_fields = tuple(
        field.name
        for field in ChurchTeachingContent._meta.fields
    )


@admin.register(ChurchTeachingScriptureReference)
class ChurchTeachingScriptureReferenceAdmin(_ReadOnlyChurchTeachingAdmin):
    list_display = (
        "content",
        "sort_order",
        "reference_text",
    )
    search_fields = (
        "reference_text",
        "content__title",
    )
    readonly_fields = tuple(
        field.name
        for field in ChurchTeachingScriptureReference._meta.fields
    )
