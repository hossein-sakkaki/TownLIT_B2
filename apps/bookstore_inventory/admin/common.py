# apps/bookstore_inventory/admin/common.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from apps.bookstore_inventory.services.access import current_warehouse_ids


BADGE_COLORS = {
    "success": ("#166534", "#dcfce7"),
    "warning": ("#92400e", "#fef3c7"),
    "danger": ("#991b1b", "#fee2e2"),
    "neutral": ("#334155", "#e2e8f0"),
}


def badge(label, tone="neutral"):
    foreground, background = BADGE_COLORS[tone]
    return format_html(
        '<span style="display:inline-block;padding:2px 8px;border-radius:999px;'
        'font-weight:600;color:{};background:{}">{}</span>',
        foreground,
        background,
        label,
    )


class WorkflowAdminMixin:
    """Small, consistent defaults used by every operational screen."""

    list_per_page = 50
    save_on_top = True
    empty_value_display = "—"
    preserve_filters = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        select_related = getattr(self, "workflow_select_related", ())
        return queryset.select_related(*select_related) if select_related else queryset

    def save_model(self, request, obj, form, change):
        if hasattr(obj, "created_by_id") and not obj.created_by_id:
            obj.created_by = request.user
        if hasattr(obj, "recorded_by_id") and not obj.recorded_by_id:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


class HiddenFromAdminIndexMixin:
    """Keep technical screens reachable from the workspace, not the app menu."""

    def get_model_perms(self, request):
        return {}


class WarehouseScopeAdminMixin:
    """Limit non-superuser Admin screens and selectors to assigned warehouses."""

    warehouse_scope_lookups = ("warehouse",)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        warehouse_ids = current_warehouse_ids(request.user)
        if not warehouse_ids:
            return queryset.none()
        scope = Q()
        for lookup in self.warehouse_scope_lookups:
            field = "pk" if lookup in {"", "pk"} else lookup
            scope |= Q(**{f"{field}__in": warehouse_ids})
        return queryset.filter(scope).distinct()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if not request.user.is_superuser:
            from apps.bookstore_inventory.models import (
                InventoryLot, Warehouse, WarehouseLocation,
            )

            warehouse_ids = current_warehouse_ids(request.user)
            if db_field.related_model is Warehouse:
                kwargs["queryset"] = Warehouse.objects.filter(pk__in=warehouse_ids)
            elif db_field.related_model is WarehouseLocation:
                kwargs["queryset"] = WarehouseLocation.objects.filter(
                    warehouse_id__in=warehouse_ids
                )
            elif db_field.related_model is InventoryLot:
                kwargs["queryset"] = InventoryLot.objects.filter(
                    warehouse_id__in=warehouse_ids
                )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class PermissionedActionsMixin:
    action_permission_map = {}

    def get_actions(self, request):
        actions = super().get_actions(request)
        for action_name, permission in self.action_permission_map.items():
            if not request.user.has_perm(permission):
                actions.pop(action_name, None)
        return actions


class ImmutableAdminMixin:
    """Audit records are viewable/searchable, but never hand-edited in Admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm(f"{self.opts.app_label}.view_{self.opts.model_name}")

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


class ProtectedAfterPostMixin:
    lock_attribute = None

    def is_locked(self, obj):
        return bool(obj and self.lock_attribute and getattr(obj, self.lock_attribute, False))

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if self.is_locked(obj):
            readonly.extend(field.name for field in self.model._meta.fields)
        return tuple(dict.fromkeys(readonly))

    def has_delete_permission(self, request, obj=None):
        if self.is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)


class ProtectedInlineMixin(admin.TabularInline):
    parent_lock_attribute = None

    def _locked(self, obj):
        return bool(obj and self.parent_lock_attribute and getattr(obj, self.parent_lock_attribute, False))

    def get_readonly_fields(self, request, obj=None):
        if self._locked(obj):
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_delete_permission(request, obj)


class SummaryChangeListMixin:
    change_list_template = "admin/bookstore_inventory/change_list_with_summary.html"
    summary_fields = ()

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        try:
            queryset = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response

        expressions = {"record_count": Count("pk")}
        has_currency = any(field.name == "currency" for field in self.model._meta.fields)
        if not has_currency:
            for field in self.summary_fields:
                expressions[field] = Coalesce(Sum(field), Decimal("0"))
        response.context_data["townlit_summary"] = queryset.aggregate(**expressions)
        if has_currency and self.summary_fields:
            currency_expressions = {
                field: Coalesce(Sum(field), Decimal("0"))
                for field in self.summary_fields
            }
            response.context_data["townlit_currency_summaries"] = list(
                queryset.values("currency").annotate(**currency_expressions).order_by("currency")
            )
        response.context_data["townlit_summary_labels"] = {
            "record_count": "Records",
            **{field: field.replace("_", " ").title() for field in self.summary_fields},
        }
        return response
