# apps/posts/admin/prayer.py

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.posts.models.pray import (
    Prayer,
    PrayerResponse,
    PrayerStatus,
)


class PrayerResponseInline(admin.StackedInline):
    """
    Inline representation of a prayer response.
    """

    model = PrayerResponse
    extra = 1
    can_delete = True

    readonly_fields = (
        "created_at",
        "updated_at",
        "is_converted",
    )

    fieldsets = (
        (
            "Result",
            {
                "fields": (
                    "result_status",
                    "response_text",
                ),
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "image",
                    "video",
                    "thumbnail",
                ),
            },
        ),
        (
            "System",
            {
                "fields": (
                    "is_converted",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )


@admin.register(Prayer)
class PrayerAdmin(admin.ModelAdmin):
    """
    Moderation and status management for prayers.
    """

    list_display = (
        "id",
        "slug",
        "owner_display",
        "status_badge",
        "media_type",
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "is_converted",
        "published_at",
    )

    list_filter = (
        "status",
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "is_converted",
        "published_at",
    )

    search_fields = (
        "slug",
        "caption",
    )

    readonly_fields = (
        "slug",
        "view_count_internal",
        "last_viewed_at",
        "published_at",
        "updated_at",
        "answered_at",
        "is_converted",
    )

    raw_id_fields = ("content_type",)
    inlines = (PrayerResponseInline,)
    ordering = ("-published_at",)
    list_per_page = 50

    list_editable = (
        "is_converted",
        "visibility",
    )

    actions = (
        "mark_waiting",
        "mark_answered",
        "mark_not_answered",
        "activate_selected",
        "deactivate_selected",
    )

    @admin.display(description="Owner")
    def owner_display(self, obj):
        try:
            owner = obj.content_object

            if owner is None:
                return "-"

            owner_user = getattr(owner, "user", None)

            if owner_user is not None:
                return (
                    getattr(owner_user, "username", None)
                    or str(owner_user)
                )

            return str(owner)
        except Exception:
            return "-"

    @admin.display(description="Status")
    def status_badge(self, obj):
        color = {
            PrayerStatus.WAITING: "#999999",
            PrayerStatus.ANSWERED: "#2ecc71",
            PrayerStatus.NOT_ANSWERED: "#e67e22",
        }.get(obj.status, "#000000")

        status_label = str(obj.status or "—").upper()

        return format_html(
            '<span style="color:white;background:{};padding:3px 8px;'
            'border-radius:12px;">{}</span>',
            color,
            status_label,
        )

    @admin.display(description="Media")
    def media_type(self, obj):
        if obj.video:
            return "Video"

        if obj.image:
            return "Image"

        return "-"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("content_type")

    @admin.action(description="Mark selected as WAITING")
    def mark_waiting(self, request, queryset):
        updated = queryset.update(status=PrayerStatus.WAITING)

        self.message_user(
            request,
            f"{updated} prayer(s) marked as WAITING.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected as ANSWERED")
    def mark_answered(self, request, queryset):
        updated = queryset.update(status=PrayerStatus.ANSWERED)

        self.message_user(
            request,
            f"{updated} prayer(s) marked as ANSWERED.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected as NOT ANSWERED")
    def mark_not_answered(self, request, queryset):
        updated = queryset.update(
            status=PrayerStatus.NOT_ANSWERED,
        )

        self.message_user(
            request,
            f"{updated} prayer(s) marked as NOT ANSWERED.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Activate selected")
    def activate_selected(self, request, queryset):
        updated = queryset.update(
            is_active=True,
            is_hidden=False,
        )

        self.message_user(
            request,
            f"{updated} prayer(s) activated.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Deactivate selected")
    def deactivate_selected(self, request, queryset):
        updated = queryset.update(is_active=False)

        self.message_user(
            request,
            f"{updated} prayer(s) deactivated.",
            level=messages.SUCCESS,
        )