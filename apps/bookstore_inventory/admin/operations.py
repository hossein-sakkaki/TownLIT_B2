# apps/bookstore_inventory/admin/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin

from apps.bookstore_inventory.admin.actions import (
    dispatch_selected_transfer,
    post_selected_adjustment,
    post_selected_return,
    post_selected_stock_count,
    receive_selected_transfer,
    snapshot_selected_stock_count,
)
from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin,
    ImmutableAdminMixin,
    PermissionedActionsMixin,
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
    DocumentStatus,
    StockCountStatus,
    TransferStatus,
)
from apps.bookstore_inventory.models import (
    InventoryLot,
    StockAdjustment,
    StockAdjustmentItem,
    StockCount,
    StockCountItem,
    StockReservation,
    StockReturn,
    StockReturnItem,
    StockTransfer,
    StockTransferItem,
    WarehouseLocation,
)
from apps.bookstore_inventory.services.access import (
    CAN_ADJUST_STOCK,
    CAN_COUNT_STOCK,
    CAN_PROCESS_RETURNS,
    CAN_TRANSFER_STOCK,
)
from apps.bookstore_inventory.services.numbering import (
    generate_adjustment_number,
    generate_return_number,
    generate_stock_count_number,
    generate_transfer_number,
)
from apps.bookstore_inventory.services.operations import (
    dispatch_stock_transfer,
    post_stock_adjustment,
    post_stock_count,
    post_stock_return,
    receive_stock_transfer,
    snapshot_stock_count,
)


class DraftOnlyInline(admin.TabularInline):
    extra = 1
    max_num = 1000
    lock_statuses = ()

    def _locked(self, obj):
        return bool(
            obj
            and obj.status in self.lock_statuses
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


class StatusLockedAdminMixin:
    editable_statuses = ()

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

        if "status" not in readonly:
            readonly.append("status")

        if (
            obj
            and obj.status
            not in self.editable_statuses
        ):
            readonly.extend(
                field.name
                for field in self.model._meta.fields
            )

        return tuple(
            dict.fromkeys(readonly)
        )


class StockTransferItemInline(DraftOnlyInline):
    model = StockTransferItem

    lock_statuses = (
        TransferStatus.DISPATCHED,
        TransferStatus.RECEIVED,
        TransferStatus.CANCELLED,
    )

    autocomplete_fields = (
        "book_edition",
        "source_location",
        "destination_location",
        "source_lot",
    )
    fields = (
        "cover",
        "book_edition",
        "source_location",
        "destination_location",
        "source_lot",
        "quantity",
        "received_quantity",
        "notes",
    )
    readonly_fields = ("cover",)

    def get_readonly_fields(
        self,
        request,
        obj=None,
    ):
        if (
            obj
            and obj.status
            == TransferStatus.DISPATCHED
        ):
            return (
                "cover",
                "book_edition",
                "source_location",
                "destination_location",
                "source_lot",
                "quantity",
                "notes",
            )

        return super().get_readonly_fields(
            request,
            obj,
        )

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        parent_id = admin_parent_object_id(
            request
        )
        transfer = None

        if parent_id:
            transfer = (
                StockTransfer.objects.filter(
                    pk=parent_id
                )
                .only(
                    "from_warehouse_id",
                    "to_warehouse_id",
                )
                .first()
            )

        if (
            db_field.name == "source_location"
            and transfer
        ):
            kwargs["queryset"] = (
                WarehouseLocation.objects.filter(
                    warehouse_id=transfer.from_warehouse_id,
                    is_active=True,
                )
            )

        elif (
            db_field.name
            == "destination_location"
            and transfer
        ):
            kwargs["queryset"] = (
                WarehouseLocation.objects.filter(
                    warehouse_id=transfer.to_warehouse_id,
                    is_active=True,
                )
            )

        elif (
            db_field.name == "source_lot"
            and transfer
        ):
            kwargs["queryset"] = (
                InventoryLot.objects.filter(
                    warehouse_id=transfer.from_warehouse_id,
                    is_active=True,
                )
            )

        elif (
            not transfer
            and not request.user.is_superuser
        ):
            warehouse_ids = (
                request_warehouse_ids(request)
                or []
            )

            if db_field.related_model is WarehouseLocation:
                kwargs["queryset"] = (
                    WarehouseLocation.objects.filter(
                        warehouse_id__in=warehouse_ids,
                        is_active=True,
                    )
                )

            elif db_field.related_model is InventoryLot:
                kwargs["queryset"] = (
                    InventoryLot.objects.filter(
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
    def cover(self, obj):
        return edition_cover_preview(
            getattr(
                obj,
                "book_edition",
                None,
            )
        )


@admin.register(StockTransfer)
class StockTransferAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WarehouseCapabilityAdminMixin,
    PermissionedActionsMixin,
    WorkflowObjectActionsMixin,
    StatusLockedAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    warehouse_scope_lookups = (
        "from_warehouse",
        "to_warehouse",
    )
    admin_capability = CAN_TRANSFER_STOCK
    editable_statuses = (
        TransferStatus.DRAFT,
    )

    actions = (
        dispatch_selected_transfer,
        receive_selected_transfer,
    )
    action_permission_map = {
        "dispatch_selected_transfer": (
            "bookstore_inventory."
            "dispatch_stocktransfer"
        ),
        "receive_selected_transfer": (
            "bookstore_inventory."
            "receive_stocktransfer"
        ),
    }

    workflow_object_actions = {
        "dispatch": {
            "label": "Dispatch transfer",
            "service": dispatch_stock_transfer,
            "id_name": "transfer_id",
            "permission": (
                "bookstore_inventory."
                "dispatch_stocktransfer"
            ),
            "available": lambda obj: (
                obj.status
                == TransferStatus.DRAFT
            ),
            "title": "Confirm transfer dispatch",
            "warning": (
                "This permanently removes the selected quantities "
                "from the source warehouse."
            ),
            "success_message": (
                "Transfer dispatched successfully."
            ),
        },
        "receive": {
            "label": "Receive transfer",
            "service": receive_stock_transfer,
            "id_name": "transfer_id",
            "permission": (
                "bookstore_inventory."
                "receive_stocktransfer"
            ),
            "available": lambda obj: (
                obj.status
                == TransferStatus.DISPATCHED
            ),
            "title": "Confirm transfer receipt",
            "warning": (
                "Verify received quantities and destination "
                "locations before continuing."
            ),
            "success_message": (
                "Transfer received successfully."
            ),
        },
    }

    list_display = (
        "transfer_number",
        "from_warehouse",
        "to_warehouse",
        "status_badge",
        "dispatched_at",
        "received_at",
        "created_by",
    )
    list_filter = (
        "status",
        "from_warehouse",
        "to_warehouse",
        "created_at",
    )
    search_fields = (
        "transfer_number",
        "notes",
        "items__book_edition__book__title",
    )
    autocomplete_fields = (
        "from_warehouse",
        "to_warehouse",
        "created_by",
        "dispatched_by",
        "received_by",
    )
    readonly_fields = (
        "transfer_number",
        "status",
        "dispatched_at",
        "received_at",
        "dispatched_by",
        "received_by",
        "created_at",
        "updated_at",
    )

    inlines = (
        StockTransferItemInline,
    )

    def get_capability_warehouse_ids(
        self,
        obj,
    ):
        if obj.status == TransferStatus.DISPATCHED:
            return {
                obj.to_warehouse_id
            }

        return {
            obj.from_warehouse_id
        }

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.transfer_number:
            obj.transfer_number = (
                generate_transfer_number()
            )

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
            (
                not obj
                or obj.status
                == TransferStatus.DRAFT
            )
            and super().has_delete_permission(
                request,
                obj,
            )
        )

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_badge(self, obj):
        if obj.status == TransferStatus.RECEIVED:
            tone = "success"
        elif obj.status == TransferStatus.DISPATCHED:
            tone = "warning"
        else:
            tone = "neutral"

        return badge(
            obj.get_status_display(),
            tone,
        )


class StockCountItemInline(DraftOnlyInline):
    model = StockCountItem

    lock_statuses = (
        StockCountStatus.POSTED,
        StockCountStatus.CANCELLED,
    )
    autocomplete_fields = (
        "book_edition",
        "lot",
    )
    fields = (
        "cover",
        "book_edition",
        "lot",
        "expected_quantity",
        "counted_quantity",
        "variance_display",
        "reason",
        "notes",
    )
    readonly_fields = (
        "cover",
        "expected_quantity",
        "variance_display",
    )

    def get_readonly_fields(
        self,
        request,
        obj=None,
    ):
        if (
            obj
            and obj.status
            in {
                StockCountStatus.COUNTING,
                StockCountStatus.SUBMITTED,
            }
        ):
            return (
                "cover",
                "book_edition",
                "lot",
                "expected_quantity",
                "variance_display",
            )

        return super().get_readonly_fields(
            request,
            obj,
        )

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        if db_field.related_model is InventoryLot:
            parent_id = admin_parent_object_id(
                request
            )

            if parent_id:
                stock_count = (
                    StockCount.objects.filter(
                        pk=parent_id
                    )
                    .only(
                        "warehouse_id",
                        "location_id",
                    )
                    .first()
                )

                if stock_count:
                    queryset = InventoryLot.objects.filter(
                        warehouse_id=stock_count.warehouse_id,
                        is_active=True,
                    )

                    if stock_count.location_id:
                        queryset = queryset.filter(
                            location_id=stock_count.location_id
                        )

                    kwargs["queryset"] = queryset

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(
            getattr(
                obj,
                "book_edition",
                None,
            )
        )

    @admin.display(description="Variance")
    def variance_display(self, obj):
        return (
            obj.variance
            if obj
            else 0
        )


@admin.register(StockCount)
class StockCountAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WarehouseCapabilityAdminMixin,
    PermissionedActionsMixin,
    WorkflowObjectActionsMixin,
    StatusLockedAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    admin_capability = CAN_COUNT_STOCK
    editable_statuses = (
        StockCountStatus.DRAFT,
    )

    actions = (
        snapshot_selected_stock_count,
        post_selected_stock_count,
    )
    action_permission_map = {
        "snapshot_selected_stock_count": (
            "bookstore_inventory."
            "snapshot_stockcount"
        ),
        "post_selected_stock_count": (
            "bookstore_inventory."
            "post_stockcount"
        ),
    }

    workflow_object_actions = {
        "snapshot": {
            "label": "Capture expected stock",
            "service": snapshot_stock_count,
            "id_name": "stock_count_id",
            "permission": (
                "bookstore_inventory."
                "snapshot_stockcount"
            ),
            "available": lambda obj: (
                obj.status
                in {
                    StockCountStatus.DRAFT,
                    StockCountStatus.COUNTING,
                }
            ),
            "title": "Capture expected quantities",
            "warning": (
                "The current system quantity will be captured "
                "as the expected quantity for each count line."
            ),
            "success_message": (
                "Expected quantities captured successfully."
            ),
        },
        "post": {
            "label": "Post count variances",
            "service": post_stock_count,
            "id_name": "stock_count_id",
            "permission": (
                "bookstore_inventory."
                "post_stockcount"
            ),
            "available": lambda obj: (
                obj.status
                in {
                    StockCountStatus.COUNTING,
                    StockCountStatus.SUBMITTED,
                }
            ),
            "title": "Confirm stock-count posting",
            "warning": (
                "This creates permanent adjustment movements "
                "for every recorded variance."
            ),
            "success_message": (
                "Stock-count variances posted successfully."
            ),
        },
    }

    list_display = (
        "count_number",
        "warehouse",
        "location",
        "status",
        "counted_at",
        "posted_at",
        "counted_by",
    )
    list_filter = (
        "status",
        "warehouse",
        "created_at",
    )
    search_fields = (
        "count_number",
        "notes",
        "items__book_edition__book__title",
    )
    autocomplete_fields = (
        "warehouse",
        "location",
        "created_by",
        "counted_by",
        "posted_by",
    )
    readonly_fields = (
        "count_number",
        "status",
        "counted_at",
        "counted_by",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at",
    )
    inlines = (
        StockCountItemInline,
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.count_number:
            obj.count_number = (
                generate_stock_count_number()
            )

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
            (
                not obj
                or obj.status
                == StockCountStatus.DRAFT
            )
            and super().has_delete_permission(
                request,
                obj,
            )
        )


class StockAdjustmentItemInline(
    DraftOnlyInline
):
    model = StockAdjustmentItem

    lock_statuses = (
        DocumentStatus.POSTED,
        DocumentStatus.CANCELLED,
    )
    autocomplete_fields = (
        "book_edition",
        "location",
        "lot",
    )
    fields = (
        "cover",
        "book_edition",
        "location",
        "lot",
        "quantity_delta",
        "notes",
    )
    readonly_fields = ("cover",)

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        parent_id = admin_parent_object_id(
            request
        )

        if parent_id:
            warehouse_id = (
                StockAdjustment.objects.filter(
                    pk=parent_id
                )
                .values_list(
                    "warehouse_id",
                    flat=True,
                )
                .first()
            )

            if warehouse_id:
                if (
                    db_field.related_model
                    is WarehouseLocation
                ):
                    kwargs["queryset"] = (
                        WarehouseLocation.objects.filter(
                            warehouse_id=warehouse_id,
                            is_active=True,
                        )
                    )

                elif (
                    db_field.related_model
                    is InventoryLot
                ):
                    kwargs["queryset"] = (
                        InventoryLot.objects.filter(
                            warehouse_id=warehouse_id,
                            is_active=True,
                        )
                    )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(
            getattr(
                obj,
                "book_edition",
                None,
            )
        )


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WarehouseCapabilityAdminMixin,
    PermissionedActionsMixin,
    WorkflowObjectActionsMixin,
    StatusLockedAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    admin_capability = CAN_ADJUST_STOCK
    editable_statuses = (
        DocumentStatus.DRAFT,
    )

    actions = (
        post_selected_adjustment,
    )
    action_permission_map = {
        "post_selected_adjustment": (
            "bookstore_inventory."
            "post_stockadjustment"
        ),
    }

    workflow_object_actions = {
        "post": {
            "label": "Post adjustment",
            "service": post_stock_adjustment,
            "id_name": "adjustment_id",
            "permission": (
                "bookstore_inventory."
                "post_stockadjustment"
            ),
            "available": lambda obj: (
                obj.status
                == DocumentStatus.DRAFT
            ),
            "title": "Confirm stock adjustment",
            "warning": (
                "This creates permanent stock movements "
                "and locks the adjustment."
            ),
            "success_message": (
                "Stock adjustment posted successfully."
            ),
        },
    }

    list_display = (
        "adjustment_number",
        "warehouse",
        "reason",
        "status",
        "posted_at",
        "created_by",
    )
    list_filter = (
        "status",
        "reason",
        "warehouse",
        "created_at",
    )
    search_fields = (
        "adjustment_number",
        "notes",
        "items__book_edition__book__title",
    )
    autocomplete_fields = (
        "warehouse",
        "created_by",
        "posted_by",
    )
    readonly_fields = (
        "adjustment_number",
        "status",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at",
    )
    inlines = (
        StockAdjustmentItemInline,
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.adjustment_number:
            obj.adjustment_number = (
                generate_adjustment_number()
            )

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
            (
                not obj
                or obj.status
                == DocumentStatus.DRAFT
            )
            and super().has_delete_permission(
                request,
                obj,
            )
        )


class StockReturnItemInline(
    DraftOnlyInline
):
    model = StockReturnItem

    lock_statuses = (
        DocumentStatus.POSTED,
        DocumentStatus.CANCELLED,
    )
    autocomplete_fields = (
        "book_edition",
        "location",
        "lot",
    )
    fields = (
        "cover",
        "book_edition",
        "location",
        "lot",
        "condition",
        "quantity",
        "notes",
    )
    readonly_fields = ("cover",)

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):
        parent_id = admin_parent_object_id(
            request
        )

        if parent_id:
            warehouse_id = (
                StockReturn.objects.filter(
                    pk=parent_id
                )
                .values_list(
                    "warehouse_id",
                    flat=True,
                )
                .first()
            )

            if warehouse_id:
                if (
                    db_field.related_model
                    is WarehouseLocation
                ):
                    kwargs["queryset"] = (
                        WarehouseLocation.objects.filter(
                            warehouse_id=warehouse_id,
                            is_active=True,
                        )
                    )

                elif (
                    db_field.related_model
                    is InventoryLot
                ):
                    kwargs["queryset"] = (
                        InventoryLot.objects.filter(
                            warehouse_id=warehouse_id,
                            is_active=True,
                        )
                    )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(
            getattr(
                obj,
                "book_edition",
                None,
            )
        )


@admin.register(StockReturn)
class StockReturnAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    WarehouseCapabilityAdminMixin,
    PermissionedActionsMixin,
    WorkflowObjectActionsMixin,
    StatusLockedAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    show_in_admin_index = True

    admin_capability = CAN_PROCESS_RETURNS
    editable_statuses = (
        DocumentStatus.DRAFT,
    )

    actions = (
        post_selected_return,
    )
    action_permission_map = {
        "post_selected_return": (
            "bookstore_inventory."
            "post_stockreturn"
        ),
    }

    workflow_object_actions = {
        "post": {
            "label": "Post return",
            "service": post_stock_return,
            "id_name": "stock_return_id",
            "permission": (
                "bookstore_inventory."
                "post_stockreturn"
            ),
            "available": lambda obj: (
                obj.status
                == DocumentStatus.DRAFT
            ),
            "title": "Confirm stock return",
            "warning": (
                "This creates permanent return movements. "
                "Verify direction, warehouse and quantities first."
            ),
            "success_message": (
                "Stock return posted successfully."
            ),
        },
    }

    list_display = (
        "return_number",
        "direction",
        "warehouse",
        "order",
        "supplier",
        "status",
        "posted_at",
    )
    list_filter = (
        "status",
        "direction",
        "warehouse",
        "created_at",
    )
    search_fields = (
        "return_number",
        "order__order_number",
        "supplier__official_name",
        "notes",
    )
    autocomplete_fields = (
        "warehouse",
        "order",
        "supplier",
        "created_by",
        "posted_by",
    )
    readonly_fields = (
        "return_number",
        "status",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at",
    )
    inlines = (
        StockReturnItemInline,
    )

    def save_model(
        self,
        request,
        obj,
        form,
        change,
    ):
        if not obj.return_number:
            obj.return_number = (
                generate_return_number()
            )

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
            (
                not obj
                or obj.status
                == DocumentStatus.DRAFT
            )
            and super().has_delete_permission(
                request,
                obj,
            )
        )


@admin.register(InventoryLot)
class InventoryLotAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    ImmutableAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    workflow_select_related = (
        "warehouse",
        "location",
        "book_edition",
        "book_edition__book",
    )
    list_display = (
        "lot_number",
        "book_edition",
        "warehouse",
        "location",
        "condition",
        "received_at",
        "on_hand_quantity",
        "is_active",
    )
    list_filter = (
        "condition",
        "warehouse",
        "is_active",
        "received_at",
    )
    search_fields = (
        "lot_number",
        "book_edition__edition_code",
        "book_edition__book__title",
    )


@admin.register(StockReservation)
class StockReservationAdmin(
    HiddenFromAdminIndexMixin,
    WarehouseScopeAdminMixin,
    ImmutableAdminMixin,
    WorkflowAdminMixin,
    admin.ModelAdmin,
):
    workflow_select_related = (
        "order_item__order",
        "warehouse",
        "book_edition",
        "book_edition__book",
        "reserved_by",
    )
    list_display = (
        "order_item",
        "book_edition",
        "warehouse",
        "quantity",
        "status",
        "reserved_at",
        "expires_at",
        "reserved_by",
    )
    list_filter = (
        "status",
        "warehouse",
        "reserved_at",
        "expires_at",
    )
    search_fields = (
        "order_item__order__order_number",
        "book_edition__book__title",
        "book_edition__edition_code",
    )