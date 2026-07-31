# apps/audio_catalog/admin/taxonomy.py

from __future__ import annotations

from django.contrib import admin

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioCategory,
    AudioContributor,
    AudioGenre,
    AudioMood,
    AudioTag,
)

from .shared import (
    LargeResultAdminMixin,
    render_json,
)


class BaseTaxonomyAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "name",
        "slug",
        "is_active",
        "sort_order",
        "updated_at",
    )

    list_editable = (
        "is_active",
        "sort_order",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "description",
        "public_id",
    )

    readonly_fields = (
        "public_id",
        "slug",
        "created_at",
        "updated_at",
    )

    ordering = (
        "sort_order",
        "name",
        "id",
    )


@admin.register(AudioCatalog)
class AudioCatalogAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "name",
        "slug",
        "visibility",
        "is_active",
        "sort_order",
        "track_count",
        "updated_at",
    )

    list_editable = (
        "is_active",
        "sort_order",
    )

    list_filter = (
        "visibility",
        "is_active",
    )

    search_fields = (
        "name",
        "slug",
        "description",
        "public_id",
    )

    readonly_fields = (
        "public_id",
        "slug",
        "track_count",
        "created_at",
        "updated_at",
    )

    ordering = (
        "sort_order",
        "name",
        "id",
    )

    @admin.display(
        description="Tracks",
    )
    def track_count(self, obj):
        if not obj or not obj.pk:
            return 0

        return obj.tracks.count()


@admin.register(AudioCategory)
class AudioCategoryAdmin(BaseTaxonomyAdmin):
    list_display = (
        "name",
        "slug",
        "icon",
        "is_active",
        "sort_order",
        "updated_at",
    )


@admin.register(AudioGenre)
class AudioGenreAdmin(BaseTaxonomyAdmin):
    pass


@admin.register(AudioMood)
class AudioMoodAdmin(BaseTaxonomyAdmin):
    pass


@admin.register(AudioTag)
class AudioTagAdmin(BaseTaxonomyAdmin):
    pass


@admin.register(AudioContributor)
class AudioContributorAdmin(
    LargeResultAdminMixin,
    admin.ModelAdmin,
):
    list_display = (
        "display_name",
        "legal_name",
        "kind",
        "is_active",
        "external_reference",
        "updated_at",
    )

    list_editable = (
        "is_active",
    )

    list_filter = (
        "kind",
        "is_active",
    )

    search_fields = (
        "display_name",
        "legal_name",
        "external_reference",
        "public_id",
    )

    readonly_fields = (
        "public_id",
        "metadata_pretty",
        "created_at",
        "updated_at",
    )

    ordering = (
        "display_name",
        "id",
    )

    @admin.display(
        description="Metadata",
    )
    def metadata_pretty(self, obj):
        return render_json(
            obj.metadata
        )