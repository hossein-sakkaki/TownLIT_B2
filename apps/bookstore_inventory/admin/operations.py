# apps/bookstore_inventory/admin/operations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin

from apps.bookstore_inventory.admin.actions import (
    dispatch_selected_transfer, post_selected_adjustment, post_selected_return,
    post_selected_stock_count, receive_selected_transfer,
    snapshot_selected_stock_count,
)
from apps.bookstore_inventory.admin.common import (
    HiddenFromAdminIndexMixin, ImmutableAdminMixin,
    PermissionedActionsMixin, WarehouseScopeAdminMixin,
    WorkflowAdminMixin, badge,
)
from apps.bookstore_inventory.admin.media import edition_cover_preview
from apps.bookstore_inventory.constants import (
    DocumentStatus, StockCountStatus, TransferStatus,
)
from apps.bookstore_inventory.models import (
    InventoryLot, StockAdjustment, StockAdjustmentItem, StockCount,
    StockCountItem, StockReservation, StockReturn, StockReturnItem,
    StockTransfer, StockTransferItem,
)
from apps.bookstore_inventory.services.numbering import (
    generate_adjustment_number, generate_return_number,
    generate_stock_count_number, generate_transfer_number,
)


class DraftOnlyInline(admin.TabularInline):
    extra = 0
    lock_statuses = ()

    def _locked(self, obj):
        return bool(obj and obj.status in self.lock_statuses)

    def get_readonly_fields(self, request, obj=None):
        if self._locked(obj):
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)

    def has_add_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return not self._locked(obj) and super().has_delete_permission(request, obj)


class StatusLockedAdminMixin:
    editable_statuses = ()

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status not in self.editable_statuses:
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)


class StockTransferItemInline(DraftOnlyInline):
    model = StockTransferItem
    lock_statuses = (TransferStatus.DISPATCHED, TransferStatus.RECEIVED, TransferStatus.CANCELLED)
    autocomplete_fields = (
        "book_edition", "source_location", "destination_location", "source_lot",
    )
    fields = (
        "cover", "book_edition", "source_location", "destination_location",
        "source_lot", "quantity", "received_quantity", "notes",
    )
    readonly_fields = ("cover",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == TransferStatus.DISPATCHED:
            return tuple(
                field.name for field in self.model._meta.fields
                if field.name != "received_quantity"
            ) + ("cover",)
        return super().get_readonly_fields(request, obj)

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(getattr(obj, "book_edition", None))


@admin.register(StockTransfer)
class StockTransferAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, PermissionedActionsMixin, StatusLockedAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    warehouse_scope_lookups = ("from_warehouse", "to_warehouse")
    editable_statuses = (TransferStatus.DRAFT,)
    actions = (dispatch_selected_transfer, receive_selected_transfer)
    action_permission_map = {
        "dispatch_selected_transfer": "bookstore_inventory.dispatch_stocktransfer",
        "receive_selected_transfer": "bookstore_inventory.receive_stocktransfer",
    }
    list_display = (
        "transfer_number", "from_warehouse", "to_warehouse", "status_badge",
        "dispatched_at", "received_at", "created_by",
    )
    list_filter = ("status", "from_warehouse", "to_warehouse", "created_at")
    search_fields = ("transfer_number", "notes", "items__book_edition__book__title")
    autocomplete_fields = ("from_warehouse", "to_warehouse", "created_by", "dispatched_by", "received_by")
    readonly_fields = (
        "transfer_number", "dispatched_at", "received_at", "dispatched_by",
        "received_by", "created_at", "updated_at",
    )
    inlines = (StockTransferItemInline,)

    def save_model(self, request, obj, form, change):
        if not obj.transfer_number:
            obj.transfer_number = generate_transfer_number()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return bool((not obj or obj.status == TransferStatus.DRAFT) and super().has_delete_permission(request, obj))

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        tone = "success" if obj.status == TransferStatus.RECEIVED else "warning" if obj.status == TransferStatus.DISPATCHED else "neutral"
        return badge(obj.get_status_display(), tone)


class StockCountItemInline(DraftOnlyInline):
    model = StockCountItem
    lock_statuses = (StockCountStatus.POSTED, StockCountStatus.CANCELLED)
    autocomplete_fields = ("book_edition", "lot")
    fields = ("cover", "book_edition", "lot", "expected_quantity", "counted_quantity", "variance_display", "reason", "notes")
    readonly_fields = ("cover", "expected_quantity", "variance_display")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status in {StockCountStatus.COUNTING, StockCountStatus.SUBMITTED}:
            editable = {"counted_quantity", "reason", "notes"}
            return tuple(
                field.name for field in self.model._meta.fields
                if field.name not in editable
            ) + ("cover", "variance_display")
        return super().get_readonly_fields(request, obj)

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(getattr(obj, "book_edition", None))

    @admin.display(description="Variance")
    def variance_display(self, obj):
        return obj.variance if obj else 0


@admin.register(StockCount)
class StockCountAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, PermissionedActionsMixin, StatusLockedAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    editable_statuses = (StockCountStatus.DRAFT,)
    actions = (snapshot_selected_stock_count, post_selected_stock_count)
    action_permission_map = {
        "snapshot_selected_stock_count": "bookstore_inventory.snapshot_stockcount",
        "post_selected_stock_count": "bookstore_inventory.post_stockcount",
    }
    list_display = ("count_number", "warehouse", "location", "status", "counted_at", "posted_at", "counted_by")
    list_filter = ("status", "warehouse", "created_at")
    search_fields = ("count_number", "notes", "items__book_edition__book__title")
    autocomplete_fields = ("warehouse", "location", "created_by", "counted_by", "posted_by")
    readonly_fields = (
        "count_number", "posted_at", "posted_by", "created_at", "updated_at",
    )
    inlines = (StockCountItemInline,)

    def save_model(self, request, obj, form, change):
        if not obj.count_number:
            obj.count_number = generate_stock_count_number()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return bool((not obj or obj.status == StockCountStatus.DRAFT) and super().has_delete_permission(request, obj))


class StockAdjustmentItemInline(DraftOnlyInline):
    model = StockAdjustmentItem
    lock_statuses = (DocumentStatus.POSTED, DocumentStatus.CANCELLED)
    autocomplete_fields = ("book_edition", "location", "lot")
    fields = ("cover", "book_edition", "location", "lot", "quantity_delta", "notes")
    readonly_fields = ("cover",)

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(getattr(obj, "book_edition", None))


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, PermissionedActionsMixin, StatusLockedAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    editable_statuses = (DocumentStatus.DRAFT,)
    actions = (post_selected_adjustment,)
    action_permission_map = {
        "post_selected_adjustment": "bookstore_inventory.post_stockadjustment",
    }
    list_display = ("adjustment_number", "warehouse", "reason", "status", "posted_at", "created_by")
    list_filter = ("status", "reason", "warehouse", "created_at")
    search_fields = ("adjustment_number", "notes", "items__book_edition__book__title")
    autocomplete_fields = ("warehouse", "created_by", "posted_by")
    readonly_fields = (
        "adjustment_number", "posted_at", "posted_by", "created_at", "updated_at",
    )
    inlines = (StockAdjustmentItemInline,)

    def save_model(self, request, obj, form, change):
        if not obj.adjustment_number:
            obj.adjustment_number = generate_adjustment_number()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return bool((not obj or obj.status == DocumentStatus.DRAFT) and super().has_delete_permission(request, obj))


class StockReturnItemInline(DraftOnlyInline):
    model = StockReturnItem
    lock_statuses = (DocumentStatus.POSTED, DocumentStatus.CANCELLED)
    autocomplete_fields = ("book_edition", "location", "lot")
    fields = ("cover", "book_edition", "location", "lot", "condition", "quantity", "notes")
    readonly_fields = ("cover",)

    @admin.display(description="Cover")
    def cover(self, obj):
        return edition_cover_preview(getattr(obj, "book_edition", None))


@admin.register(StockReturn)
class StockReturnAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, PermissionedActionsMixin, StatusLockedAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    editable_statuses = (DocumentStatus.DRAFT,)
    actions = (post_selected_return,)
    action_permission_map = {
        "post_selected_return": "bookstore_inventory.post_stockreturn",
    }
    list_display = ("return_number", "direction", "warehouse", "order", "supplier", "status", "posted_at")
    list_filter = ("status", "direction", "warehouse", "created_at")
    search_fields = ("return_number", "order__order_number", "supplier__official_name", "notes")
    autocomplete_fields = ("warehouse", "order", "supplier", "created_by", "posted_by")
    readonly_fields = (
        "return_number", "posted_at", "posted_by", "created_at", "updated_at",
    )
    inlines = (StockReturnItemInline,)

    def save_model(self, request, obj, form, change):
        if not obj.return_number:
            obj.return_number = generate_return_number()
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return bool((not obj or obj.status == DocumentStatus.DRAFT) and super().has_delete_permission(request, obj))


@admin.register(InventoryLot)
class InventoryLotAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, ImmutableAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    workflow_select_related = ("warehouse", "location", "book_edition", "book_edition__book")
    list_display = ("lot_number", "book_edition", "warehouse", "location", "condition", "received_at", "on_hand_quantity", "is_active")
    list_filter = ("condition", "warehouse", "is_active", "received_at")
    search_fields = ("lot_number", "book_edition__edition_code", "book_edition__book__title")


@admin.register(StockReservation)
class StockReservationAdmin(HiddenFromAdminIndexMixin, WarehouseScopeAdminMixin, ImmutableAdminMixin, WorkflowAdminMixin, admin.ModelAdmin):
    workflow_select_related = ("order_item__order", "warehouse", "book_edition", "book_edition__book", "reserved_by")
    list_display = ("order_item", "book_edition", "warehouse", "quantity", "status", "reserved_at", "expires_at", "reserved_by")
    list_filter = ("status", "warehouse", "reserved_at", "expires_at")
    search_fields = ("order_item__order__order_number", "book_edition__book__title", "book_edition__edition_code")
