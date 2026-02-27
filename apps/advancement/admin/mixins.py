# apps/advancement/admin/mixins.py

import csv
from django.http import HttpResponse
from apps.advancement.permissions import is_advancement_officer


class AdvancementRoleAdminMixin:
    """Shared role checks for advancement admin classes."""

    def has_module_permission(self, request):
        return self.admin_site.has_permission(request)

    def has_view_permission(self, request, obj=None):
        return self.admin_site.has_permission(request)

    def has_change_permission(self, request, obj=None):
        return is_advancement_officer(request.user)

    def has_add_permission(self, request):
        return is_advancement_officer(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_advancement_officer(request.user)

    def get_readonly_fields(self, request, obj=None):
        """Board viewers get full read-only access."""
        base_ro = list(getattr(super(), "readonly_fields", []))
        if not is_advancement_officer(request.user):
            base_ro.extend([f.name for f in self.model._meta.fields])
            base_ro.extend([m2m.name for m2m in self.model._meta.many_to_many])
        return tuple(dict.fromkeys(base_ro))

    def changelist_view(self, request, extra_context=None):
        """Add board-mode flag for templates."""
        extra_context = extra_context or {}
        extra_context["adv_board_readonly"] = not is_advancement_officer(request.user)
        return super().changelist_view(request, extra_context=extra_context)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """Add board-mode flag for templates."""
        extra_context = extra_context or {}
        extra_context["adv_board_readonly"] = not is_advancement_officer(request.user)
        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)


class CSVExportAdminMixin:
    """CSV export action with support for related lookups (e.g. external_entity__name)."""

    csv_export_fields = None  # Set per admin class

    @staticmethod
    def _resolve_attr(obj, field_path: str):
        """Resolve nested attrs using __ notation."""
        current = obj
        for part in field_path.split("__"):
            if current is None:
                return ""
            current = getattr(current, part, None)
            if callable(current):
                current = current()
        return "" if current is None else current

    def export_as_csv(self, request, queryset):
        meta = self.model._meta
        fields = self.csv_export_fields or [f.name for f in meta.fields]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{meta.model_name}_export.csv"'

        writer = csv.writer(response)
        writer.writerow(fields)

        for obj in queryset:
            row = [str(self._resolve_attr(obj, f)) for f in fields]
            writer.writerow(row)

        return response

    export_as_csv.short_description = "Export selected rows to CSV"