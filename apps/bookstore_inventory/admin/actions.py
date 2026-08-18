# apps/bookstore_inventory/admin/actions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.template.response import TemplateResponse

from apps.bookstore_inventory.services.inventory import fulfill_book_order, post_inbound_shipment_to_stock
from apps.bookstore_inventory.services.operations import (
    dispatch_stock_transfer, post_stock_adjustment, post_stock_count,
    post_stock_return, receive_stock_transfer, snapshot_stock_count,
)
from apps.bookstore_inventory.services.reservations import reserve_book_order


def _confirmed(request):
    return request.POST.get("confirm_irreversible") == "yes"


def _confirmation_page(modeladmin, request, queryset, title, warning, action_name):
    return TemplateResponse(
        request,
        "admin/bookstore_inventory/confirm_workflow_action.html",
        {
            **modeladmin.admin_site.each_context(request),
            "opts": modeladmin.model._meta,
            "title": title,
            "warning": warning,
            "queryset": queryset,
            "action_name": action_name,
            "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
        },
    )


def _run_service(modeladmin, request, queryset, service, id_name, label):
    succeeded = 0
    failed = 0
    for obj in queryset:
        try:
            service(**{id_name: obj.pk, "user": request.user})
            succeeded += 1
        except ValidationError as exc:
            failed += 1
            modeladmin.message_user(request, f"{obj}: {exc}", messages.ERROR)
    if succeeded:
        modeladmin.message_user(request, f"{succeeded} {label}(s) completed.", messages.SUCCESS)
    if failed:
        modeladmin.message_user(request, f"{failed} {label}(s) were not changed.", messages.WARNING)


@admin.action(description="Post selected inbound shipment to stock")
def post_selected_shipments_to_stock(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one shipment per posting.", messages.WARNING)
        return None
    if not _confirmed(request):
        return _confirmation_page(
            modeladmin,
            request,
            queryset,
            "Confirm stock posting",
            "This creates permanent stock movements and locks the shipment details.",
            "post_selected_shipments_to_stock",
        )
    _run_service(modeladmin, request, queryset, post_inbound_shipment_to_stock, "shipment_id", "shipment")


@admin.action(description="Fulfil selected order and deduct stock")
def fulfill_selected_orders(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one order per fulfilment.", messages.WARNING)
        return None
    if not _confirmed(request):
        return _confirmation_page(
            modeladmin,
            request,
            queryset,
            "Confirm order fulfilment",
            "This deducts stock and locks the order lines. Verify warehouse, items and quantities first.",
            "fulfill_selected_orders",
        )
    _run_service(modeladmin, request, queryset, fulfill_book_order, "order_id", "order")


@admin.action(description="Reserve stock for selected order")
def reserve_selected_order(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one order.", messages.WARNING)
        return None
    _run_service(modeladmin, request, queryset, reserve_book_order, "order_id", "order reservation")


def _confirmed_single_action(modeladmin, request, queryset, *, service, id_name, label, title, warning, action_name):
    if queryset.count() != 1:
        modeladmin.message_user(request, f"Select exactly one {label}.", messages.WARNING)
        return None
    if not _confirmed(request):
        return _confirmation_page(modeladmin, request, queryset, title, warning, action_name)
    _run_service(modeladmin, request, queryset, service, id_name, label)


@admin.action(description="Dispatch selected stock transfer")
def dispatch_selected_transfer(modeladmin, request, queryset):
    return _confirmed_single_action(
        modeladmin, request, queryset, service=dispatch_stock_transfer,
        id_name="transfer_id", label="transfer", title="Confirm transfer dispatch",
        warning="This permanently removes the selected quantities from the source warehouse.",
        action_name="dispatch_selected_transfer",
    )


@admin.action(description="Receive selected stock transfer")
def receive_selected_transfer(modeladmin, request, queryset):
    return _confirmed_single_action(
        modeladmin, request, queryset, service=receive_stock_transfer,
        id_name="transfer_id", label="transfer", title="Confirm transfer receipt",
        warning="Verify received quantities and destination locations before continuing.",
        action_name="receive_selected_transfer",
    )


@admin.action(description="Capture expected quantities for selected stock count")
def snapshot_selected_stock_count(modeladmin, request, queryset):
    if queryset.count() != 1:
        modeladmin.message_user(request, "Select exactly one stock count.", messages.WARNING)
        return None
    _run_service(modeladmin, request, queryset, snapshot_stock_count, "stock_count_id", "stock count")


@admin.action(description="Post selected stock count variances")
def post_selected_stock_count(modeladmin, request, queryset):
    return _confirmed_single_action(
        modeladmin, request, queryset, service=post_stock_count,
        id_name="stock_count_id", label="stock count", title="Confirm stock-count posting",
        warning="This creates permanent adjustment movements for every variance.",
        action_name="post_selected_stock_count",
    )


@admin.action(description="Post selected stock adjustment")
def post_selected_adjustment(modeladmin, request, queryset):
    return _confirmed_single_action(
        modeladmin, request, queryset, service=post_stock_adjustment,
        id_name="adjustment_id", label="adjustment", title="Confirm stock adjustment",
        warning="This creates permanent stock movements and locks the adjustment.",
        action_name="post_selected_adjustment",
    )


@admin.action(description="Post selected stock return")
def post_selected_return(modeladmin, request, queryset):
    return _confirmed_single_action(
        modeladmin, request, queryset, service=post_stock_return,
        id_name="stock_return_id", label="return", title="Confirm stock return",
        warning="This creates permanent return movements. Verify direction and quantities.",
        action_name="post_selected_return",
    )
