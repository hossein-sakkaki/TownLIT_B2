# apps/accounts/admin/label_admin.py

from django.contrib import admin
from colorfield.fields import ColorField
from django import forms

from ..models import CustomLabel


@admin.register(CustomLabel)
class CustomLabelAdmin(admin.ModelAdmin):

    list_display = [
        "name",
        "color",
        "description",
        "is_active",
    ]

    search_fields = [
        "name",
        "description",
    ]

    list_editable = [
        "is_active",
    ]

    list_filter = [
        "is_active",
    ]

    ordering = [
        "name",
    ]

    formfield_overrides = {
        ColorField: {"widget": forms.TextInput(attrs={"type": "color"})},
    }