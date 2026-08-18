# apps/bookstore_inventory/admin/warehouse.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html, format_html_join

from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, WorkflowAdminMixin,
)
from apps.bookstore_inventory.models import (
    Warehouse, WarehouseLocation, WarehouseStaffAssignment,
)
from apps.bookstore_inventory.forms.warehouse import (
    WarehouseStaffAssignmentAdminForm,
)



def _disable_user_related_actions(form_class):
    """
    Warehouse administration may only select an existing user.

    Remove Admin's add/change/delete/view related-object controls so this
    screen can never open CustomUser creation or modification forms.
    """
    user_field = form_class.base_fields.get("user")
    if not user_field:
        return form_class

    widget = user_field.widget

    for attribute in (
        "can_add_related",
        "can_change_related",
        "can_delete_related",
        "can_view_related",
    ):
        if hasattr(widget, attribute):
            setattr(widget, attribute, False)

    return form_class


class WarehouseStaffAssignmentInline(admin.StackedInline):
    model = WarehouseStaffAssignment
    form = WarehouseStaffAssignmentAdminForm
    extra = 1

    fieldsets = (
        (
            None,
            {
                "fields": (
                    ("user", "role", "is_active"),
                    "account_contact",
                    ("starts_at", "ends_at"),
                ),
            },
        ),
        (
            "Operator capabilities",
            {
                "fields": (
                    (
                        "can_receive_stock",
                        "can_fulfill_orders",
                        "can_transfer_stock",
                    ),
                    (
                        "can_count_stock",
                        "can_adjust_stock",
                        "can_process_returns",
                    ),
                ),
                "description": (
                    "Primary managers and managers automatically receive all "
                    "capabilities. These switches apply to Operator assignments."
                ),
            },
        ),
        ("Notes", {"fields": ("notes",), "classes": ("collapse",)}),
    )

    readonly_fields = ("account_contact",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        _disable_user_related_actions(formset.form)
        return formset

    @admin.display(description="Contact from CustomUser")
    def account_contact(self, obj):
        if not obj or not obj.user_id:
            return "Select a user and save to display the account contact."
        return _user_contact(obj.user)

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    

class WarehouseLocationInline(admin.TabularInline):
    model = WarehouseLocation
    extra = 1
    fields = ("code", "name", "location_type", "parent", "is_pickable", "is_active")
    autocomplete_fields = ("parent",)


@admin.register(Warehouse)
class WarehouseAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    warehouse_scope_lookups = ("pk",)
    list_display = (
        "name", "code", "city", "country", "responsible_staff",
        "total_on_hand", "total_reserved", "is_active",
    )
    list_filter = ("is_active", "country")
    search_fields = ("name", "code", "city", "province_state", "country")
    readonly_fields = ("created_at", "updated_at")
    inlines = (WarehouseStaffAssignmentInline, WarehouseLocationInline)
    fieldsets = (
        ("Identity", {"fields": (("name", "code"), "is_active")}),
        (
            "Address",
            {
                "fields": (
                    "address_line_1", "address_line_2", ("city", "province_state"),
                    ("postal_code", "country"),
                ),
            },
        ),
        (
            "Operational responsibility",
            {
                "fields": ("responsibility_summary",),
                "description": (
                    "Responsibility and contact details come directly from CustomUser "
                    "accounts through the Staff assignments below. No duplicate name "
                    "or phone number is stored on the warehouse."
                ),
            },
        ),
        ("Description", {"fields": ("description",)}),
        (
            "Audit",
            {"fields": (("created_at", "updated_at"),), "classes": ("collapse",)},
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "responsibility_summary")

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related(
            "staff_assignments__user"
        ).annotate(
            _total_on_hand=Sum("balances__on_hand_quantity"),
            _total_reserved=Sum("balances__reserved_quantity"),
        )

    @admin.display(description="On hand", ordering="_total_on_hand")
    def total_on_hand(self, obj):
        return obj._total_on_hand or 0

    @admin.display(description="Reserved", ordering="_total_reserved")
    def total_reserved(self, obj):
        return obj._total_reserved or 0

    @admin.display(description="Responsible staff")
    def responsible_staff(self, obj):
        assignments = [
            assignment
            for assignment in obj.staff_assignments.all()
            if assignment.is_current
        ]
        return ", ".join(
            f"{_user_name(assignment.user)} ({assignment.get_role_display()})"
            for assignment in assignments
        ) or "—"

    @admin.display(description="Current managers and operators")
    def responsibility_summary(self, obj):
        if not obj or not obj.pk:
            return "Save the warehouse, then add responsible CustomUser accounts below."

        assignments = [
            assignment
            for assignment in obj.staff_assignments.select_related("user")
            if assignment.is_current
        ]
        if not assignments:
            return format_html(
                '<span style="color:#92400e;font-weight:600">{}</span>',
                "No active staff assignment. Add at least one manager below.",
            )

        return format_html_join(
            "",
            (
                '<div style="margin:0 0 10px;padding:10px 12px;'
                'border:1px solid rgba(0,0,0,.12);border-radius:8px">'
                '<strong>{}</strong> — {}<br>{}'
                "</div>"
            ),
            (
                (
                    _user_name(assignment.user),
                    assignment.get_role_display(),
                    _user_contact(assignment.user),
                )
                for assignment in assignments
            ),
        )


@admin.register(WarehouseLocation)
class WarehouseLocationAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    workflow_select_related = ("warehouse", "parent")
    list_display = ("code", "name", "warehouse", "location_type", "parent", "is_pickable", "is_active")
    list_filter = ("warehouse", "location_type", "is_pickable", "is_active")
    search_fields = ("code", "name", "warehouse__name", "warehouse__code")
    autocomplete_fields = ("warehouse", "parent")


@admin.register(WarehouseStaffAssignment)
class WarehouseStaffAssignmentAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    form = WarehouseStaffAssignmentAdminForm
    workflow_select_related = ("warehouse", "user")

    list_display = (
        "user",
        "warehouse",
        "role",
        "current_status",
        "starts_at",
        "ends_at",
    )
    list_filter = ("role", "is_active", "warehouse")
    search_fields = (
        "warehouse__name",
        "warehouse__code",
        "user__username",
        "user__email",
    )

    # Warehouse remains searchable; user uses the filtered existing-user list.
    autocomplete_fields = ("warehouse",)

    readonly_fields = ("created_at", "updated_at")

    def get_form(self, request, obj=None, change=False, **kwargs):
        form_class = super().get_form(
            request,
            obj=obj,
            change=change,
            **kwargs,
        )
        return _disable_user_related_actions(form_class)

    @admin.display(description="Current", boolean=True)
    def current_status(self, obj):
        return obj.is_current

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


def _user_name(user):
    full_name = " ".join(
        part.strip()
        for part in (
            getattr(user, "name", "") or "",
            getattr(user, "family", "") or "",
        )
        if part.strip()
    )
    return full_name or getattr(user, "username", "") or getattr(user, "email", "") or str(user)


def _user_contact(user):
    email = (getattr(user, "email", "") or "").strip()
    phone = (getattr(user, "mobile_number", "") or "").strip()
    parts = [part for part in (email, phone) if part]
    return " · ".join(parts) or "No email or phone is stored on this account."
