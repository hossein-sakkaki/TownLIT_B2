# apps/bookstore_inventory/admin/orders.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin

from apps.bookstore_inventory.admin.actions import (
    fulfill_selected_orders,
    reserve_selected_order,
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
    badge,
)
from apps.bookstore_inventory.admin.media import (
    edition_cover_preview,
)
from apps.bookstore_inventory.constants import (
    OrderStatus,
)
from apps.bookstore_inventory.forms.orders import (
    BookOrderAdminForm,
)
from apps.bookstore_inventory.models import (
    Warehouse,
    WarehouseLocation,
)
from apps.bookstore_inventory.models.orders import (
    BookOrder,
    BookOrderItem,
    PaymentRecord,
)
from apps.bookstore_inventory.services.access import (
    CAN_FULFILL_ORDERS,
    current_warehouse_ids,
)
from apps.bookstore_inventory.services.inventory import (
    fulfill_book_order,
)
from apps.bookstore_inventory.services.numbering import (
    generate_order_number,
)
from apps.bookstore_inventory.services.reports import (
    scoped_book_orders_queryset,
)
from apps.bookstore_inventory.services.reservations import (
    reserve_book_order,
)


class BookOrderItemInline(
    ProtectedInlineMixin
):
    model = BookOrderItem
    parent_lock_attribute = "is_fulfilled"

    extra = 1
    max_num = 1000

    autocomplete_fields = (
        "book_edition",
        "warehouse",
        "location",
    )
    fields = (
        "cover_preview",
        "book_edition",
        "warehouse",
        "location",
        "quantity",
        "unit_price",
        "line_total",
        "pricing_mode_snapshot",
        "notes",
    )
    readonly_fields = (
        "cover_preview",
        "line_total",
        "pricing_mode_snapshot",
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
        if not request.user.is_superuser:
            warehouse_ids = current_warehouse_ids(
                request.user
            )

            if db_field.related_model is Warehouse:
                kwargs["queryset"] = (
                    Warehouse.objects.filter(
                        pk__in=warehouse_ids,
                        is_active=True,
                    )
                )

            elif (
                db_field.related_model
                is WarehouseLocation
            ):
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


class PaymentRecordInline(admin.TabularInline):
    model = PaymentRecord

    extra = 1
    max_num = 500

    fields = (
        "amount",
        "currency",
        "payment_method",
        "payment_status",
        "transaction_reference",
        "received_at",
        "received_by",
        "notes",
    )
    autocomplete_fields = ("received_by",)

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return bool(
            (not obj or not obj.is_fulfilled)
            and super().has_delete_permission(
                request,
                obj,
            )
        )


@admin.register(BookOrder)
class BookOrderAdmin(
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

    warehouse_scope_lookups = (
        "items__warehouse",
    )
    admin_capability = CAN_FULFILL_ORDERS

    form = BookOrderAdminForm
    lock_attribute = "is_fulfilled"

    summary_fields = (
        "total_amount",
        "paid_amount",
        "remaining_amount",
    )

    actions = (
        reserve_selected_order,
        fulfill_selected_orders,
    )
    action_permission_map = {
        "reserve_selected_order": (
            "bookstore_inventory."
            "reserve_bookorder"
        ),
        "fulfill_selected_orders": (
            "bookstore_inventory."
            "fulfill_bookorder"
        ),
    }

    workflow_object_actions = {
        "reserve": {
            "label": "Reserve stock",
            "service": reserve_book_order,
            "id_name": "order_id",
            "permission": (
                "bookstore_inventory."
                "reserve_bookorder"
            ),
            "available": lambda obj: (
                not obj.is_fulfilled
                and obj.status
                != OrderStatus.CANCELLED
            ),
            "title": "Confirm stock reservation",
            "warning": (
                "This will reserve the current order quantities "
                "from the selected warehouses."
            ),
            "success_message": (
                "Stock reserved for the order successfully."
            ),
        },
        "fulfil": {
            "label": "Fulfil order",
            "service": fulfill_book_order,
            "id_name": "order_id",
            "permission": (
                "bookstore_inventory."
                "fulfill_bookorder"
            ),
            "available": lambda obj: (
                not obj.is_fulfilled
                and obj.status
                != OrderStatus.CANCELLED
            ),
            "title": "Confirm order fulfilment",
            "warning": (
                "This permanently deducts stock and locks "
                "the order lines. Verify quantities, warehouses "
                "and payment information before continuing."
            ),
            "success_message": (
                "Order fulfilled successfully."
            ),
        },
    }

    workflow_select_related = (
        "recipient_organization",
        "created_by",
        "fulfilled_by",
    )

    list_display = (
        "order_number",
        "recipient",
        "order_type",
        "purpose",
        "delivery_method",
        "created_at",
        "total_amount",
        "remaining_amount",
        "payment_badge",
        "fulfilment_badge",
    )
    list_filter = (
        "status",
        "order_type",
        "recipient_type",
        "purpose",
        "delivery_method",
        "payment_status",
        "currency",
        "fulfilled_at",
        "created_at",
    )
    search_fields = (
        "order_number",
        "recipient_first_name",
        "recipient_last_name",
        "recipient_email",
        "recipient_phone",
        "organization_name",
        "organization_contact_person",
        "organization_email",
        "organization_phone",
        "recipient_organization__official_name",
        "recipient_organization__aliases__name",
    )
    autocomplete_fields = (
        "recipient_organization",
        "created_by",
        "fulfilled_by",
    )
    readonly_fields = (
        "order_number",
        "status",
        "subtotal_amount",
        "total_amount",
        "paid_amount",
        "remaining_amount",
        "payment_status",
        "fulfilled_at",
        "fulfilled_by",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"

    inlines = (
        BookOrderItemInline,
        PaymentRecordInline,
    )

    fieldsets = (
        (
            "1. Order",
            {
                "fields": (
                    (
                        "order_number",
                        "order_type",
                        "status",
                    ),
                    (
                        "purpose",
                        "currency",
                    ),
                ),
                "description": (
                    "Order status is controlled by the workflow. "
                    "Do not change fulfilment state manually."
                ),
            },
        ),
        (
            "2. Recipient",
            {
                "fields": (
                    "recipient_type",
                    "recipient_organization",
                    (
                        "recipient_first_name",
                        "recipient_last_name",
                    ),
                    (
                        "recipient_email",
                        "recipient_phone",
                    ),
                    "organization_name",
                    "organization_contact_person",
                    (
                        "organization_email",
                        "organization_phone",
                    ),
                ),
                "description": (
                    "For organization orders, choose the reusable "
                    "directory record. Snapshot fields preserve "
                    "historical contact details."
                ),
            },
        ),
        (
            "3. Delivery",
            {
                "fields": (
                    (
                        "delivery_method",
                        "destination_name",
                    ),
                    "address_line_1",
                    "address_line_2",
                    (
                        "city",
                        "province_state",
                    ),
                    (
                        "postal_code",
                        "country",
                    ),
                )
            },
        ),
        (
            "4. Financial summary",
            {
                "fields": (
                    (
                        "subtotal_amount",
                        "donation_amount",
                        "discount_amount",
                    ),
                    (
                        "total_amount",
                        "paid_amount",
                        "remaining_amount",
                    ),
                    "payment_status",
                ),
                "description": (
                    "Totals are calculated from order lines "
                    "and successful payment records."
                ),
            },
        ),
        (
            "5. Fulfilment",
            {
                "fields": (
                    (
                        "fulfilled_at",
                        "fulfilled_by",
                    ),
                ),
                "description": (
                    "Use Reserve stock or Fulfil order above. "
                    "Fulfilment state cannot be set manually."
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

    def get_capability_warehouse_ids(
        self,
        obj,
    ):
        return set(
            obj.items.values_list(
                "warehouse_id",
                flat=True,
            )
        )

    def get_queryset(self, request):
        queryset = super().get_queryset(
            request
        )

        if request.user.is_superuser:
            return queryset

        warehouse_ids = current_warehouse_ids(
            request.user
        )

        allowed_ids = (
            scoped_book_orders_queryset(
                warehouse_ids
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

        return queryset.filter(
            pk__in=allowed_ids
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.order_number:
            obj.order_number = (
                generate_order_number()
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
        form.instance.recalculate_totals(
            save=True
        )

    @admin.display(description="Recipient")
    def recipient(self, obj):
        return obj.recipient_display

    @admin.display(
        description="Payment",
        ordering="payment_status",
    )
    def payment_badge(self, obj):
        if obj.payment_status == "paid":
            tone = "success"
        elif obj.payment_status == "partial":
            tone = "warning"
        else:
            tone = "danger"

        return badge(
            obj.get_payment_status_display(),
            tone,
        )

    @admin.display(description="Order")
    def fulfilment_badge(self, obj):
        return badge(
            (
                "Fulfilled"
                if obj.is_fulfilled
                else obj.get_status_display()
            ),
            (
                "success"
                if obj.is_fulfilled
                else "warning"
            ),
        )


@admin.register(PaymentRecord)
class PaymentRecordAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    warehouse_scope_lookups = (
        "order__items__warehouse",
    )
    workflow_select_related = (
        "order",
        "received_by",
    )

    list_display = (
        "received_at",
        "order",
        "amount",
        "currency",
        "payment_method",
        "payment_status",
        "transaction_reference",
        "received_by",
    )
    list_filter = (
        "payment_method",
        "payment_status",
        "currency",
        "received_at",
    )
    search_fields = (
        "order__order_number",
        "transaction_reference",
        "notes",
    )
    autocomplete_fields = (
        "order",
        "received_by",
    )
    date_hierarchy = "received_at"

    def get_queryset(self, request):
        queryset = super().get_queryset(
            request
        )

        if request.user.is_superuser:
            return queryset

        warehouse_ids = current_warehouse_ids(
            request.user
        )

        order_ids = (
            scoped_book_orders_queryset(
                warehouse_ids
            )
            .values_list(
                "pk",
                flat=True,
            )
        )

        return queryset.filter(
            order_id__in=order_ids
        )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.received_by_id:
            obj.received_by = request.user

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
        return bool(
            obj
            and not obj.order.is_fulfilled
            and super().has_delete_permission(
                request,
                obj,
            )
        )