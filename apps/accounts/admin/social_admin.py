# apps/accounts/admin/social_admin.py

from django.contrib import admin

from ..models import SocialMediaType


@admin.register(SocialMediaType)
class SocialMediaTypeAdmin(admin.ModelAdmin):

    list_display = [
        "name",
        "icon_class",
        "is_active",
    ]

    search_fields = [
        "name",
    ]

    list_editable = [
        "is_active",
    ]

    list_filter = [
        "is_active",
    ]