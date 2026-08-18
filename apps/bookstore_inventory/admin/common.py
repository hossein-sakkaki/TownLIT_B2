# apps/bookstore_inventory/admin/common.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.db import models
from django.contrib import admin, messages
from django.contrib.admin.utils import quote, unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from apps.bookstore_inventory.models import WarehouseStaffAssignment
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


def admin_parent_object_id(request):
    resolver_match = getattr(request, "resolver_match", None)
    if not resolver_match:
        return None
    object_id = resolver_match.kwargs.get("object_id")
    if object_id in {None, ""}:
        return None
    return unquote(str(object_id))


def request_warehouse_ids(request):
    if request.user.is_superuser:
        return None
    return current_warehouse_ids(request.user)


def _current_capability_assignments(user, warehouse_ids=None):
    if (
        user is None
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
    ):
        return []

    now = timezone.now()
    queryset = WarehouseStaffAssignment.objects.select_related(
        "warehouse",
        "user",
    ).filter(
        user=user,
        is_active=True,
        starts_at__lte=now,
    ).filter(
        Q(ends_at__isnull=True) | Q(ends_at__gt=now)
    )

    if warehouse_ids is not None:
        queryset = queryset.filter(warehouse_id__in=warehouse_ids)

    return list(queryset)


def user_has_warehouse_capability(
    *,
    user,
    capability,
    warehouse_ids=None,
):
    if getattr(user, "is_superuser", False):
        return True

    requested_ids = {
        int(warehouse_id)
        for warehouse_id in (warehouse_ids or [])
        if warehouse_id is not None
    }

    assignments = _current_capability_assignments(
        user,
        requested_ids if requested_ids else None,
    )
    allowed_ids = {
        assignment.warehouse_id
        for assignment in assignments
        if assignment.allows(capability)
    }

    if requested_ids:
        return requested_ids.issubset(allowed_ids)

    return bool(allowed_ids)


class WorkflowAdminMixin:
    """Small, consistent defaults used by every operational screen."""

    list_per_page = 50
    save_on_top = True
    empty_value_display = "—"
    preserve_filters = True

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        select_related = getattr(self, "workflow_select_related", ())
        return (
            queryset.select_related(*select_related)
            if select_related
            else queryset
        )

    def save_model(self, request, obj, form, change):
        if hasattr(obj, "created_by_id") and not obj.created_by_id:
            obj.created_by = request.user
        if hasattr(obj, "recorded_by_id") and not obj.recorded_by_id:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


class HiddenFromAdminIndexMixin:
    """
    Keep technical screens hidden while allowing important operational
    models to remain directly reachable from the Django Admin index.
    """

    show_in_admin_index = False

    def get_model_perms(self, request):
        if self.show_in_admin_index:
            return super().get_model_perms(request)
        return {}


class WarehouseScopeAdminMixin:
    """Limit non-superuser screens and selectors to assigned warehouses."""

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
                InventoryLot,
                Warehouse,
                WarehouseLocation,
            )

            warehouse_ids = current_warehouse_ids(request.user)

            if db_field.related_model is Warehouse:
                kwargs["queryset"] = Warehouse.objects.filter(
                    pk__in=warehouse_ids
                )

            elif db_field.related_model is WarehouseLocation:
                kwargs["queryset"] = WarehouseLocation.objects.filter(
                    warehouse_id__in=warehouse_ids
                )

            elif db_field.related_model is InventoryLot:
                kwargs["queryset"] = InventoryLot.objects.filter(
                    warehouse_id__in=warehouse_ids
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )


class WarehouseCapabilityAdminMixin:
    """
    Capability-aware CRUD protection.

    Django permissions remain necessary, but operational editing also requires
    a current warehouse assignment with the configured capability.
    """

    admin_capability = None

    def get_capability_warehouse_ids(self, obj):
        warehouse_id = getattr(obj, "warehouse_id", None)
        return {warehouse_id} if warehouse_id else set()

    def _has_admin_capability(self, request, obj=None):
        if not self.admin_capability:
            return True

        if request.user.is_superuser:
            return True

        warehouse_ids = (
            self.get_capability_warehouse_ids(obj)
            if obj is not None
            else None
        )

        return user_has_warehouse_capability(
            user=request.user,
            capability=self.admin_capability,
            warehouse_ids=warehouse_ids,
        )

    def has_add_permission(self, request):
        return bool(
            super().has_add_permission(request)
            and self._has_admin_capability(request)
        )

    def has_change_permission(self, request, obj=None):
        return bool(
            super().has_change_permission(request, obj)
            and self._has_admin_capability(request, obj)
        )

    def has_delete_permission(self, request, obj=None):
        return bool(
            super().has_delete_permission(request, obj)
            and self._has_admin_capability(request, obj)
        )


class PermissionedActionsMixin:
    action_permission_map = {}

    def get_actions(self, request):
        actions = super().get_actions(request)

        for action_name, permission in self.action_permission_map.items():
            if not request.user.has_perm(permission):
                actions.pop(action_name, None)

        return actions


class WorkflowObjectActionsMixin:
    """
    Adds explicit workflow buttons to the object change page.

    Each action still calls the authoritative service layer. GET never changes
    state; the user always reaches a confirmation screen first.
    """

    change_form_template = (
        "admin/bookstore_inventory/change_form_with_workflow.html"
    )
    workflow_object_actions = {}

    def get_urls(self):
        opts = self.model._meta
        custom_urls = (
            path(
                "<path:object_id>/workflow/<slug:workflow_action>/",
                self.admin_site.admin_view(
                    self.workflow_object_action_view
                ),
                name=(
                    f"{opts.app_label}_{opts.model_name}_"
                    "workflow_action"
                ),
            ),
        )
        return list(custom_urls) + super().get_urls()

    def _workflow_action_definition(self, action_name):
        return self.workflow_object_actions.get(action_name)

    def _workflow_action_available(self, definition, obj):
        available = definition.get("available")
        if available is None:
            return True

        if isinstance(available, str):
            available = getattr(self, available)

        return bool(available(obj))

    def _workflow_action_permitted(
        self,
        request,
        obj,
        definition,
    ):
        permission = definition.get("permission")
        if permission and not request.user.has_perm(permission):
            return False

        return self.has_change_permission(request, obj)

    def get_visible_workflow_actions(self, request, obj):
        if obj is None:
            return []

        opts = self.model._meta
        visible = []

        for action_name, definition in self.workflow_object_actions.items():
            if not self._workflow_action_permitted(
                request,
                obj,
                definition,
            ):
                continue

            if not self._workflow_action_available(
                definition,
                obj,
            ):
                continue

            visible.append({
                "name": action_name,
                "label": definition["label"],
                "tone": definition.get("tone", "primary"),
                "url": reverse(
                    (
                        f"admin:{opts.app_label}_{opts.model_name}_"
                        "workflow_action"
                    ),
                    args=[quote(obj.pk), action_name],
                    current_app=self.admin_site.name,
                ),
            })

        return visible

    def changeform_view(
        self,
        request,
        object_id=None,
        form_url="",
        extra_context=None,
    ):
        context = dict(extra_context or {})

        if object_id:
            obj = self.get_object(
                request,
                unquote(str(object_id)),
            )
            if obj is not None:
                context["townlit_workflow_actions"] = (
                    self.get_visible_workflow_actions(
                        request,
                        obj,
                    )
                )

        return super().changeform_view(
            request,
            object_id=object_id,
            form_url=form_url,
            extra_context=context,
        )

    def workflow_object_action_view(
        self,
        request,
        object_id,
        workflow_action,
    ):
        obj = self.get_object(
            request,
            unquote(str(object_id)),
        )
        if obj is None:
            raise Http404

        definition = self._workflow_action_definition(
            workflow_action
        )
        if definition is None:
            raise Http404

        if not self._workflow_action_permitted(
            request,
            obj,
            definition,
        ):
            raise PermissionDenied

        opts = self.model._meta
        change_url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change",
            args=[quote(obj.pk)],
            current_app=self.admin_site.name,
        )

        if not self._workflow_action_available(
            definition,
            obj,
        ):
            self.message_user(
                request,
                "This workflow action is no longer available for this record.",
                level=messages.WARNING,
            )
            return HttpResponseRedirect(change_url)

        if request.method == "POST":
            service = definition["service"]
            id_name = definition["id_name"]

            try:
                service(
                    **{
                        id_name: obj.pk,
                        "user": request.user,
                    }
                )
            except ValidationError as exc:
                self.message_user(
                    request,
                    str(exc),
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    definition.get(
                        "success_message",
                        f"{definition['label']} completed successfully.",
                    ),
                    level=messages.SUCCESS,
                )

            return HttpResponseRedirect(change_url)

        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            "admin/bookstore_inventory/confirm_object_workflow.html",
            {
                **self.admin_site.each_context(request),
                "opts": opts,
                "title": definition.get(
                    "title",
                    definition["label"],
                ),
                "warning": definition.get(
                    "warning",
                    "Confirm that you want to continue.",
                ),
                "object": obj,
                "action_label": definition["label"],
                "cancel_url": change_url,
            },
        )


class ImmutableAdminMixin:
    """Audit records are viewable/searchable, but never hand-edited."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm(
            f"{self.opts.app_label}.view_{self.opts.model_name}"
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(
            field.name
            for field in self.model._meta.fields
        )


class ProtectedAfterPostMixin:
    lock_attribute = None

    def is_locked(self, obj):
        return bool(
            obj
            and self.lock_attribute
            and getattr(obj, self.lock_attribute, False)
        )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(
            super().get_readonly_fields(request, obj)
        )

        if self.is_locked(obj):
            readonly.extend(
                field.name
                for field in self.model._meta.fields
            )

        return tuple(dict.fromkeys(readonly))

    def has_delete_permission(self, request, obj=None):
        if self.is_locked(obj):
            return False
        return super().has_delete_permission(request, obj)


class ProtectedInlineMixin(admin.TabularInline):
    parent_lock_attribute = None

    def _locked(self, obj):
        return bool(
            obj
            and self.parent_lock_attribute
            and getattr(
                obj,
                self.parent_lock_attribute,
                False,
            )
        )

    def get_readonly_fields(
        self,
        request,
        obj=None,
    ):
        readonly = list(
            super().get_readonly_fields(
                request,
                obj,
            )
        )

        if self._locked(obj):
            readonly.extend(
                field.name
                for field in self.model._meta.fields
            )

        return tuple(
            dict.fromkeys(readonly)
        )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return bool(
            not self._locked(obj)
            and super().has_add_permission(
                request,
                obj,
            )
        )

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return bool(
            not self._locked(obj)
            and super().has_delete_permission(
                request,
                obj,
            )
        )


class SummaryChangeListMixin:
    change_list_template = (
        "admin/bookstore_inventory/change_list_with_summary.html"
    )
    summary_fields = ()

    def _summary_sum_expression(self, field_name):
        """
        Build a type-safe SUM expression for IntegerField, DecimalField,
        FloatField, and other numeric model fields.

        Explicit output_field prevents Django from mixing the type of the
        aggregated model field with the fallback zero value.
        """
        model_field = self.model._meta.get_field(field_name)

        if isinstance(model_field, models.DecimalField):
            fallback = Value(
                Decimal("0"),
                output_field=model_field,
            )
        elif isinstance(model_field, models.FloatField):
            fallback = Value(
                0.0,
                output_field=model_field,
            )
        else:
            fallback = Value(
                0,
                output_field=model_field,
            )

        return Coalesce(
            Sum(field_name),
            fallback,
            output_field=model_field,
        )

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(
            request,
            extra_context=extra_context,
        )

        try:
            queryset = response.context_data["cl"].queryset
        except (AttributeError, KeyError):
            return response

        expressions = {
            "record_count": Count("pk"),
        }

        has_currency = any(
            field.name == "currency"
            for field in self.model._meta.fields
        )

        if not has_currency:
            for field_name in self.summary_fields:
                expressions[field_name] = (
                    self._summary_sum_expression(field_name)
                )

        summary = queryset.aggregate(**expressions)

        labels = {
            "record_count": "Records",
            **{
                field_name: field_name.replace("_", " ").title()
                for field_name in self.summary_fields
            },
        }

        response.context_data["townlit_summary"] = summary
        response.context_data["townlit_summary_labels"] = labels
        response.context_data["townlit_summary_rows"] = [
            {
                "key": key,
                "label": labels.get(
                    key,
                    key.replace("_", " ").title(),
                ),
                "value": value,
            }
            for key, value in summary.items()
        ]

        if has_currency and self.summary_fields:
            currency_expressions = {
                field_name: self._summary_sum_expression(field_name)
                for field_name in self.summary_fields
            }

            raw_groups = list(
                queryset.values("currency")
                .annotate(**currency_expressions)
                .order_by("currency")
            )

            response.context_data[
                "townlit_currency_summaries"
            ] = raw_groups

            response.context_data[
                "townlit_currency_summary_rows"
            ] = [
                {
                    "currency": group["currency"],
                    "metrics": [
                        {
                            "label": labels.get(
                                field_name,
                                field_name.replace("_", " ").title(),
                            ),
                            "value": group[field_name],
                        }
                        for field_name in self.summary_fields
                    ],
                }
                for group in raw_groups
            ]

        return response