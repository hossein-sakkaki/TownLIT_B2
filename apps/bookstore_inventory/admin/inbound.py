# apps/bookstore_inventory/admin/inbound.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal

from django.contrib import admin
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.bookstore_inventory.admin.actions import (
    post_selected_shipments_to_stock,
)
from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin,
    PermissionedActionsMixin,
    ProtectedAfterPostMixin,
    ProtectedInlineMixin,
    SummaryChangeListMixin,
    WarehouseCapabilityAdminMixin,
    WarehouseScopeAdminMixin,
    WorkflowAdminMixin,
    WorkflowObjectActionsMixin,
    admin_parent_object_id,
    badge,
    request_warehouse_ids,
)
from apps.bookstore_inventory.admin.media import (
    edition_cover_preview,
)
from apps.bookstore_inventory.constants import (
    InboundPaymentScheduleStatus,
)
from apps.bookstore_inventory.forms import (
    InboundShipmentAdminForm,
)
from apps.bookstore_inventory.models import (
    InboundPayment,
    InboundPaymentSchedule,
    InboundShipment,
    InboundShipmentItem,
    WarehouseLocation,
)
from apps.bookstore_inventory.services.access import (
    CAN_RECEIVE_STOCK,
)
from apps.bookstore_inventory.services.inventory import (
    post_inbound_shipment_to_stock,
)
from apps.bookstore_inventory.services.numbering import (
    generate_shipment_number,
)


class InboundShipmentItemInline(
    ProtectedInlineMixin
):
    model = InboundShipmentItem
    parent_lock_attribute = "is_stock_posted"

    extra = 1
    max_num = 1000

    autocomplete_fields = (
        "book_edition",
        "location",
    )
    fields = (
        "cover_preview",
        "book_edition",
        "location",
        "lot_number",
        "condition",
        "quantity",
        "unit_cost",
        "line_total",
        "notes",
    )
    readonly_fields = (
        "cover_preview",
        "line_total",
    )

    def get_queryset(self, request):
        return super().get_queryset(
            request
        ).select_related(
            "book_edition__book"
        )

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        if db_field.related_model is WarehouseLocation:
            parent_id = admin_parent_object_id(
                request
            )

            if parent_id:
                warehouse_id = (
                    InboundShipment.objects.filter(
                        pk=parent_id
                    )
                    .values_list(
                        "warehouse_id",
                        flat=True,
                    )
                    .first()
                )

                if warehouse_id:
                    kwargs["queryset"] = (
                        WarehouseLocation.objects.filter(
                            warehouse_id=warehouse_id,
                            is_active=True,
                        )
                    )

            elif not request.user.is_superuser:
                warehouse_ids = (
                    request_warehouse_ids(request)
                    or []
                )
                kwargs["queryset"] = (
                    WarehouseLocation.objects.filter(
                        warehouse_id__in=warehouse_ids,
                        is_active=True,
                    )
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    @admin.display(description="Cover")
    def cover_preview(self, obj):
        edition = getattr(
            obj,
            "book_edition",
            None,
        )
        return edition_cover_preview(edition)


class InboundPaymentInline(admin.TabularInline):
    model = InboundPayment

    extra = 1
    max_num = 500

    fields = (
        "schedule",
        "amount",
        "currency",
        "settlement_amount",
        "settlement_currency",
        "exchange_rate",
        "payment_reference",
        "paid_at",
        "recorded_by",
        "notes",
    )
    autocomplete_fields = (
        "schedule",
        "recorded_by",
    )

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        if db_field.related_model is InboundPaymentSchedule:
            parent_id = admin_parent_object_id(
                request
            )
            if parent_id:
                kwargs["queryset"] = (
                    InboundPaymentSchedule.objects.filter(
                        shipment_id=parent_id
                    ).order_by(
                        "due_date",
                        "pk",
                    )
                )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return bool(
            (not obj or not obj.is_stock_posted)
            and super().has_delete_permission(
                request,
                obj,
            )
        )


class InboundPaymentScheduleInline(
    admin.TabularInline
):
    model = InboundPaymentSchedule

    extra = 1
    max_num = 500
    can_delete = False

    fields = (
        "due_date",
        "description",
        "amount",
        "currency",
        "status",
        "paid_amount_display",
        "remaining_amount_display",
        "overdue_display",
    )
    readonly_fields = (
        "status",
        "paid_amount_display",
        "remaining_amount_display",
        "overdue_display",
    )

    @admin.display(description="Paid")
    def paid_amount_display(self, obj):
        return (
            obj.paid_amount
            if obj and obj.pk
            else 0
        )

    @admin.display(description="Remaining")
    def remaining_amount_display(self, obj):
        return (
            obj.remaining_amount
            if obj and obj.pk
            else 0
        )

    @admin.display(
        description="Overdue",
        boolean=True,
    )
    def overdue_display(self, obj):
        return bool(
            obj
            and obj.pk
            and obj.is_overdue
        )


class PaymentScheduleDueFilter(
    admin.SimpleListFilter
):
    title = "Due state"
    parameter_name = "due_state"

    def lookups(self, request, model_admin):
        return (
            ("overdue", "Overdue"),
            (
                "upcoming",
                "Upcoming/open",
            ),
        )

    def queryset(
        self,
        request,
        queryset,
    ):
        today = timezone.localdate()

        if self.value() == "overdue":
            return queryset.exclude(
                status=InboundPaymentScheduleStatus.PAID
            ).filter(
                due_date__lt=today
            )

        if self.value() == "upcoming":
            return queryset.exclude(
                status=InboundPaymentScheduleStatus.PAID
            ).filter(
                due_date__gte=today
            )

        return queryset


@admin.register(InboundShipment)
class InboundShipmentAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WarehouseCapabilityAdminMixin,
    PermissionedActionsMixin,
    WorkflowObjectActionsMixin,
    ProtectedAfterPostMixin,
    SummaryChangeListMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True
    admin_capability = CAN_RECEIVE_STOCK

    form = InboundShipmentAdminForm
    lock_attribute = "is_stock_posted"

    summary_fields = (
        "total_cost",
        "amount_paid",
        "amount_due",
    )

    actions = (
        post_selected_shipments_to_stock,
    )
    action_permission_map = {
        "post_selected_shipments_to_stock": (
            "bookstore_inventory."
            "post_inboundshipment"
        ),
    }

    workflow_object_actions = {
        "post_to_stock": {
            "label": "Post to stock",
            "service": post_inbound_shipment_to_stock,
            "id_name": "shipment_id",
            "permission": (
                "bookstore_inventory."
                "post_inboundshipment"
            ),
            "available": (
                lambda obj: not obj.is_stock_posted
            ),
            "title": "Confirm stock posting",
            "warning": (
                "This creates permanent stock movements and "
                "locks the shipment details. Verify all items, "
                "quantities, locations, costs and payment data first."
            ),
            "success_message": (
                "Inbound shipment posted to stock successfully."
            ),
        },
    }

    workflow_select_related = (
        "warehouse",
        "supplier",
        "donor",
        "created_by",
        "stock_posted_by",
    )

    list_display = (
        "shipment_number",
        "warehouse",
        "source_type",
        "supplier",
        "donor",
        "received_at",
        "total_cost",
        "amount_due",
        "overdue_amount_display",
        "payment_badge",
        "stock_badge",
    )
    list_filter = (
        "warehouse",
        "source_type",
        "payment_status",
        "is_consignment",
        "currency",
        "stock_posted_at",
        "received_at",
    )
    search_fields = (
        "shipment_number",
        "supplier_name",
        "donor_name",
        "supplier__official_name",
        "donor__official_name",
        "invoice_reference",
        "supplier_contact",
        "supplier_phone",
    )
    autocomplete_fields = (
        "warehouse",
        "supplier",
        "donor",
        "created_by",
        "stock_posted_by",
    )
    readonly_fields = (
        "shipment_number",
        "subtotal_cost",
        "total_cost",
        "amount_paid",
        "amount_due",
        "payment_status",
        "payment_plan_summary",
        "stock_posted_at",
        "stock_posted_by",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "received_at"

    inlines = (
        InboundShipmentItemInline,
        InboundPaymentScheduleInline,
        InboundPaymentInline,
    )

    fieldsets = (
        (
            "1. Receiving",
            {
                "fields": (
                    (
                        "shipment_number",
                        "warehouse",
                    ),
                    (
                        "source_type",
                        "received_at",
                    ),
                )
            },
        ),
        (
            "2. Organizations",
            {
                "fields": (
                    ("supplier", "donor"),
                    (
                        "supplier_name",
                        "donor_name",
                    ),
                    (
                        "supplier_contact",
                        "supplier_phone",
                    ),
                    "invoice_reference",
                ),
                "description": (
                    "Select reusable organizations. "
                    "Snapshot names preserve the document history."
                ),
            },
        ),
        (
            "3. Costs and payment",
            {
                "fields": (
                    (
                        "currency",
                        "shipping_cost",
                        "other_cost",
                    ),
                    (
                        "subtotal_cost",
                        "total_cost",
                    ),
                    (
                        "amount_paid",
                        "amount_due",
                        "payment_status",
                    ),
                    "payment_plan_summary",
                )
            },
        ),
        (
            "Consignment",
            {
                "fields": (
                    "is_consignment",
                    "consignment_notes",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "4. Stock posting",
            {
                "fields": (
                    (
                        "stock_posted_at",
                        "stock_posted_by",
                    ),
                ),
                "description": (
                    "Use the Post to stock workflow button after "
                    "checking all item lines."
                ),
            },
        ),
        (
            "Notes and audit",
            {
                "fields": (
                    "notes",
                    "created_by",
                    (
                        "created_at",
                        "updated_at",
                    ),
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(
            request
        ).prefetch_related(
            "payment_schedules__payments"
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.shipment_number:
            obj.shipment_number = (
                generate_shipment_number()
            )

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def save_related(
        self,
        request,
        form,
        formsets,
        change,
    ):
        super().save_related(
            request,
            form,
            formsets,
            change,
        )

        form.instance.amount_paid = sum(
            (
                payment.amount
                for payment
                in form.instance.payments.all()
            ),
            0,
        )
        form.instance.recalculate_totals(
            save=True
        )

    def save_formset(
        self,
        request,
        form,
        formset,
        change,
    ):
        for inline_form in formset.forms:
            instance = inline_form.instance

            if (
                isinstance(
                    instance,
                    InboundPaymentSchedule,
                )
                and not instance.created_by_id
            ):
                instance.created_by = request.user

            if (
                isinstance(
                    instance,
                    InboundPayment,
                )
                and not instance.recorded_by_id
            ):
                instance.recorded_by = request.user

        super().save_formset(
            request,
            form,
            formset,
            change,
        )

    @admin.display(
        description="Payment",
        ordering="payment_status",
    )
    def payment_badge(self, obj):
        if obj.payment_status in {
            "paid",
            "not_required",
        }:
            tone = "success"
        elif obj.payment_status == "partial":
            tone = "warning"
        else:
            tone = "danger"

        return badge(
            obj.get_payment_status_display(),
            tone,
        )

    @admin.display(description="Stock")
    def stock_badge(self, obj):
        return badge(
            (
                "Posted"
                if obj.is_stock_posted
                else "Draft"
            ),
            (
                "success"
                if obj.is_stock_posted
                else "warning"
            ),
        )

    @admin.display(description="Overdue")
    def overdue_amount_display(self, obj):
        amount = obj.overdue_amount

        return badge(
            (
                f"{amount} {obj.currency}"
                if amount
                else "None"
            ),
            (
                "danger"
                if amount
                else "success"
            ),
        )

    @admin.display(description="Payment plan")
    def payment_plan_summary(self, obj):
        if not obj or not obj.pk:
            return (
                "Save the shipment to add "
                "payment due dates."
            )

        return (
            f"Outstanding: {obj.amount_due} {obj.currency} | "
            f"Scheduled remaining: "
            f"{obj.scheduled_remaining_amount} {obj.currency} | "
            f"Unplanned: "
            f"{obj.unplanned_due_amount} {obj.currency} | "
            f"Overdue: "
            f"{obj.overdue_amount} {obj.currency}"
        )


@admin.register(InboundPaymentSchedule)
class InboundPaymentScheduleAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    SummaryChangeListMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    warehouse_scope_lookups = (
        "shipment__warehouse",
    )
    summary_fields = ("amount",)

    workflow_select_related = (
        "shipment",
        "shipment__supplier",
        "created_by",
    )
    list_display = (
        "due_date",
        "shipment",
        "supplier",
        "amount",
        "currency",
        "paid_amount_display",
        "remaining_amount_display",
        "status_badge",
        "overdue_display",
    )
    list_filter = (
        PaymentScheduleDueFilter,
        "status",
        "currency",
        "due_date",
        "shipment__supplier",
    )
    search_fields = (
        "shipment__shipment_number",
        "shipment__supplier__official_name",
        "description",
        "notes",
    )
    autocomplete_fields = (
        "shipment",
        "created_by",
    )
    readonly_fields = (
        "status",
        "paid_amount_display",
        "remaining_amount_display",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "due_date"

    def get_queryset(self, request):
        return super().get_queryset(
            request
        ).annotate(
            _paid_amount=Coalesce(
                Sum("payments__amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=2,
                ),
            )
        )

    def _paid(self, obj):
        annotated = getattr(
            obj,
            "_paid_amount",
            None,
        )
        return (
            obj.paid_amount
            if annotated is None
            else annotated
        )

    def _remaining(self, obj):
        return max(
            obj.amount - self._paid(obj),
            Decimal("0.00"),
        )

    def _overdue(self, obj):
        return bool(
            self._remaining(obj)
            > Decimal("0.00")
            and obj.due_date
            < timezone.localdate()
        )

    @admin.display(description="Supplier")
    def supplier(self, obj):
        return obj.shipment.supplier or "—"

    @admin.display(description="Paid")
    def paid_amount_display(self, obj):
        return self._paid(obj)

    @admin.display(description="Remaining")
    def remaining_amount_display(self, obj):
        return self._remaining(obj)

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_badge(self, obj):
        tone = (
            "success"
            if obj.status
            == InboundPaymentScheduleStatus.PAID
            else "warning"
        )

        if self._overdue(obj):
            tone = "danger"

        return badge(
            obj.get_status_display(),
            tone,
        )

    @admin.display(
        description="Overdue",
        boolean=True,
    )
    def overdue_display(self, obj):
        return self._overdue(obj)

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(
            request,
            obj,
            form,
            change,
        )

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        if obj and obj.payments.exists():
            return False

        return super().has_delete_permission(
            request,
            obj,
        )


@admin.register(InboundPayment)
class InboundPaymentAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    warehouse_scope_lookups = (
        "shipment__warehouse",
    )
    workflow_select_related = (
        "shipment",
        "recorded_by",
    )
    list_display = (
        "paid_at",
        "shipment",
        "schedule",
        "amount",
        "currency",
        "settlement_display",
        "payment_reference",
        "recorded_by",
    )
    list_filter = (
        "currency",
        "settlement_currency",
        "paid_at",
    )
    search_fields = (
        "shipment__shipment_number",
        "payment_reference",
        "notes",
    )
    autocomplete_fields = (
        "shipment",
        "schedule",
        "recorded_by",
    )
    date_hierarchy = "paid_at"

    @admin.display(description="Cash settlement")
    def settlement_display(self, obj):
        return (
            f"{obj.cash_amount} "
            f"{obj.cash_currency}"
        )

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return bool(
            obj
            and not obj.shipment.is_stock_posted
            and super().has_delete_permission(
                request,
                obj,
            )
        )