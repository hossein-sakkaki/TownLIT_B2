# apps/audio_catalog/admin/taxonomy.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from django.contrib import admin
from django.db.models import Count

from apps.audio_catalog.models import (
    AudioCatalog,
    AudioCategory,
    AudioContributor,
    AudioGenre,
    AudioMood,
    AudioTag,
)
from .forms import AudioContributorAdminForm

from .shared import LargeResultAdminMixin


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
    list_filter = ("is_active",)
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

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            admin_track_count=Count("tracks", distinct=True)
        )

    @admin.display(description="Tracks", ordering="admin_track_count")
    def track_count(self, obj):
        if not obj or not obj.pk:
            return 0

        return getattr(obj, "admin_track_count", 0)


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
    form = AudioContributorAdminForm

    list_display = (
        "display_name",
        "legal_name",
        "kind",
        "is_active",
        "external_reference",
        "updated_at",
    )

    list_editable = ("is_active",)
    list_filter = ("kind", "is_active")

    search_fields = (
        "display_name",
        "legal_name",
        "external_reference",
        "public_id",
    )

    search_help_text = (
        "Search by display name, legal name, external reference, "
        "or public ID."
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "updated_at",
    )

    ordering = (
        "display_name",
        "legal_name",
        "id",
    )

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "display_name",
                    "legal_name",
                    "kind",
                    "is_active",
                ),
            },
        ),
        (
            "References",
            {
                "fields": (
                    "website_url",
                    "external_reference",
                ),
            },
        ),
        (
            "Metadata",
            {
                "classes": ("collapse",),
                "fields": ("metadata",),
            },
        ),
        (
            "System",
            {
                "classes": ("collapse",),
                "fields": (
                    "public_id",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )