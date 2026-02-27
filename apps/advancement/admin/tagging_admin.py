# apps/advancement/admin/tagging_admin.py

from django.contrib import admin
from apps.advancement.models import Tag, TagCategory
from .mixins import AdvancementRoleAdminMixin, CSVExportAdminMixin


@admin.register(TagCategory, site=None)
class TagCategoryAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    actions = ("export_as_csv",)


@admin.register(Tag, site=None)
class TagAdmin(AdvancementRoleAdminMixin, CSVExportAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "category")
    list_filter = ("category",)
    search_fields = ("name", "slug")
    actions = ("export_as_csv",)