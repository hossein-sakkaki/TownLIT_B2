# apps/posts/admin/common.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html


class MarkActiveMixin:
    """
    Shared bulk actions for models containing an is_active field.
    """

    @admin.action(description="Mark selected items as inactive")
    def make_inactive(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"{updated} selected item(s) marked as inactive.",
        )

    @admin.action(description="Mark selected items as active")
    def make_active(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"{updated} selected item(s) marked as active.",
        )


def admin_change_link_for_instance(obj):
    """
    Build a safe admin change link for a model instance.

    Plain text is returned when the model is not registered in admin,
    the object has no primary key, or its admin URL cannot be resolved.
    """
    if obj is None:
        return "-"

    try:
        opts = obj._meta
        url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=[obj.pk],
        )
        return format_html('<a href="{}">{}</a>', url, str(obj))
    except Exception:
        return str(obj)


def admin_change_link_for_ct_and_pk(content_type, object_id):
    """
    Build a safe admin link from ContentType and object_id.
    """
    if content_type is None or object_id is None:
        return "-"

    fallback = (
        f"{content_type.app_label}."
        f"{content_type.model}#{object_id}"
    )

    try:
        model_class = content_type.model_class()

        if model_class is None:
            return fallback

        target = model_class._default_manager.filter(pk=object_id).first()

        if target is None:
            return fallback

        return admin_change_link_for_instance(target)
    except Exception:
        return fallback