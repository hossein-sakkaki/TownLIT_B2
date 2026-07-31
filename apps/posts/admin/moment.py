# apps/posts/admin/moment.py

from django.contrib import admin

from apps.posts.models.moment import Moment


@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    """
    Moderation-friendly and visibility-aware admin for moments.
    """

    list_display = (
        "id",
        "owner_display",
        "media_type",
        "visibility",
        "is_converted",
        "is_active",
        "is_hidden",
        "is_suspended",
        "reactions_count",
        "comments_count",
        "published_at",
    )

    list_filter = (
        "visibility",
        "is_active",
        "is_hidden",
        "is_suspended",
        "published_at",
    )

    search_fields = (
        "caption",
        "object_id",
    )

    ordering = ("-published_at",)
    date_hierarchy = "published_at"
    list_select_related = ("content_type",)
    list_per_page = 50

    readonly_fields = (
        "id",
        "owner_display",
        "reactions_count",
        "recomments_count",
        "comments_count",
        "reactions_breakdown",
        "view_count_internal",
        "last_viewed_at",
        "published_at",
        "updated_at",
    )

    list_editable = ("visibility",)

    fieldsets = (
        (
            "Owner",
            {
                "fields": (
                    "owner_display",
                    "content_type",
                    "object_id",
                ),
            },
        ),
        (
            "Content",
            {
                "fields": (
                    "caption",
                    "image",
                    "video",
                    "thumbnail",
                ),
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "visibility",
                    "is_hidden",
                    "is_converted",
                ),
            },
        ),
        (
            "Moderation",
            {
                "fields": (
                    "is_active",
                    "is_suspended",
                    "reports_count",
                    "suspended_at",
                    "suspension_reason",
                ),
            },
        ),
        (
            "Interactions (denormalized)",
            {
                "fields": (
                    "reactions_count",
                    "reactions_breakdown",
                    "comments_count",
                    "recomments_count",
                ),
            },
        ),
        (
            "Analytics",
            {
                "fields": (
                    "view_count_internal",
                    "last_viewed_at",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "published_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Owner", ordering="object_id")
    def owner_display(self, obj):
        content_type = getattr(obj, "content_type", None)
        object_id = getattr(obj, "object_id", None)

        if content_type is None or object_id is None:
            return "Unknown"

        return f"{content_type.model} #{object_id}"

    @admin.display(description="Media")
    def media_type(self, obj):
        if obj.image:
            return "Image"

        if obj.video:
            return "Video"

        return "-"