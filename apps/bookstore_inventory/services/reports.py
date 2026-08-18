# apps/bookstore_inventory/services/reports.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from collections import OrderedDict, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.bookstore_inventory.constants import (
    CashEntryDirection,
    STOCK_IN_TYPES,
    STOCK_OUT_TYPES,
    StockMovementType,
)
from apps.bookstore_inventory.models import (
    BookOrder,
    BookOrderItem,
    CashLedgerEntry,
    InboundPayment,
    InboundPaymentSchedule,
    InboundShipment,
    InventoryBalance,
    PaymentRecord,
    StockMovement,
    StockTransfer,
    Warehouse,
)
from apps.bookstore_inventory.services.access import current_warehouse_ids


REPORT_DEFINITIONS = OrderedDict((
    (
        "current_inventory",
        {
            "label": "Current inventory",
            "description": "On-hand, reserved, unavailable, and available quantities by warehouse and edition.",
            "permission": "bookstore_inventory.view_inventorybalance",
            "dated": False,
        },
    ),
    (
        "stock_activity",
        {
            "label": "Stock activity",
            "description": "Opening, incoming, outgoing, net, and closing quantities for a date range.",
            "permission": "bookstore_inventory.view_stockmovement",
            "dated": True,
        },
    ),
    (
        "movement_detail",
        {
            "label": "Movement detail",
            "description": "The immutable line-by-line audit trail for every stock change.",
            "permission": "bookstore_inventory.view_stockmovement",
            "dated": True,
        },
    ),
    (
        "inbound",
        {
            "label": "Inbound and acquisition",
            "description": "Received shipments, sources, posting state, acquisition cost, and outstanding amount.",
            "permission": "bookstore_inventory.view_inboundshipment",
            "dated": True,
        },
    ),
    (
        "orders",
        {
            "label": "Orders and distribution",
            "description": "Sales, gifts, donation-based distributions, fulfilment, and payment status.",
            "permission": "bookstore_inventory.view_bookorder",
            "dated": True,
        },
    ),
    (
        "transfers",
        {
            "label": "Warehouse transfers",
            "description": "Stock dispatched and received between TownLIT warehouses.",
            "permission": "bookstore_inventory.view_stocktransfer",
            "dated": True,
        },
    ),
    (
        "supplier_payables",
        {
            "label": "Supplier payables",
            "description": "Scheduled, paid, remaining, and overdue supplier instalments.",
            "permission": "bookstore_inventory.view_inboundpaymentschedule",
            "dated": True,
        },
    ),
    (
        "cash_ledger",
        {
            "label": "Cash ledger",
            "description": "Cash received and paid, grouped safely by currency.",
            "permission": "bookstore_inventory.view_cashledgerentry",
            "dated": True,
        },
    ),
))


class ReportValidationError(ValueError):
    pass


def available_report_definitions(user):
    if not getattr(user, "is_authenticated", False):
        return []
    return [
        {"code": code, **definition}
        for code, definition in REPORT_DEFINITIONS.items()
        if getattr(user, "is_superuser", False)
        or user.has_perm(definition["permission"])
    ]


def report_warehouse_ids(user):
    if getattr(user, "is_superuser", False):
        return list(Warehouse.objects.values_list("pk", flat=True))
    return list(current_warehouse_ids(user))


def report_warehouses(user):
    return Warehouse.objects.filter(
        pk__in=report_warehouse_ids(user)
    ).order_by("name", "pk")


def _parse_requested_date(value, label):
    if not value:
        return None
    parsed = parse_date(str(value))
    if parsed is None:
        raise ReportValidationError(f"{label} must be a valid date.")
    return parsed


def _filters(params, *, code, warehouse_ids):
    definition = REPORT_DEFINITIONS[code]
    today = timezone.localdate()
    date_from = _parse_requested_date(params.get("date_from"), "From date")
    date_to = _parse_requested_date(params.get("date_to"), "To date")
    if code == "supplier_payables":
        # Show every overdue instalment plus the next quarter by default.
        date_to = date_to or today + timedelta(days=90)
    elif definition["dated"]:
        date_to = date_to or today
        date_from = date_from or date_to - timedelta(days=29)
    if date_from and date_to and date_from > date_to:
        raise ReportValidationError("From date cannot be after To date.")

    warehouse_id = None
    requested_warehouse = str(params.get("warehouse") or "").strip()
    if requested_warehouse:
        try:
            warehouse_id = int(requested_warehouse)
        except (TypeError, ValueError) as exc:
            raise ReportValidationError("Warehouse selection is invalid.") from exc
        if warehouse_id not in warehouse_ids:
            raise ReportValidationError("You do not have access to that warehouse.")

    movement_type = str(params.get("movement_type") or "").strip()
    valid_movement_types = {value for value, _label in StockMovementType.choices}
    if movement_type and movement_type not in valid_movement_types:
        raise ReportValidationError("Movement type is invalid.")

    return {
        "date_from": date_from,
        "date_to": date_to,
        "warehouse_id": warehouse_id,
        "warehouse": requested_warehouse,
        "query": str(params.get("query") or "").strip()[:160],
        "movement_type": movement_type,
        "currency": str(params.get("currency") or "").strip().upper()[:12],
    }


def _scope_warehouse(queryset, filters, lookup="warehouse_id"):
    if filters["warehouse_id"]:
        return queryset.filter(**{lookup: filters["warehouse_id"]})
    return queryset


def _date_scope(queryset, filters, field):
    if filters["date_from"]:
        queryset = queryset.filter(**{f"{field}__date__gte": filters["date_from"]})
    if filters["date_to"]:
        queryset = queryset.filter(**{f"{field}__date__lte": filters["date_to"]})
    return queryset


def _currency_cards(groups):
    return [
        {
            "currency": currency,
            "metrics": [
                {
                    "label": key.replace("_", " ").title(),
                    "value": value,
                }
                for key, value in values.items()
            ],
        }
        for currency, values in sorted(groups.items())
    ]


def _column(label, *, numeric=False):
    return {"label": label, "numeric": numeric}


def _result(code, filters, *, columns, rows, totals=(), currency_totals=(), truncated=False):
    definition = REPORT_DEFINITIONS[code]
    return {
        "code": code,
        "title": definition["label"],
        "description": definition["description"],
        "columns": columns,
        "rows": rows,
        "totals": list(totals),
        "currency_totals": list(currency_totals),
        "filters": filters,
        "truncated": truncated,
        "filename": f"townlit-{code}-{timezone.localdate().isoformat()}.csv",
    }


def _current_inventory(filters, warehouse_ids, row_limit):
    queryset = InventoryBalance.objects.filter(
        warehouse_id__in=warehouse_ids
    ).select_related("warehouse", "book_edition__book")
    queryset = _scope_warehouse(queryset, filters)
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(book_edition__book__title__icontains=query)
            | Q(book_edition__edition_code__icontains=query)
            | Q(book_edition__edition_name__icontains=query)
            | Q(book_edition__isbn__icontains=query)
            | Q(book_edition__barcode__icontains=query)
            | Q(book_edition__language__icontains=query)
        )
    queryset = queryset.order_by(
        "warehouse__name", "book_edition__book__title", "book_edition__edition_code"
    )
    total_count = queryset.count()
    aggregate = queryset.aggregate(
        on_hand=Coalesce(Sum("on_hand_quantity"), Value(0)),
        reserved=Coalesce(Sum("reserved_quantity"), Value(0)),
        unavailable=Coalesce(Sum("unavailable_quantity"), Value(0)),
    )
    aggregate["available"] = (
        aggregate["on_hand"] - aggregate["reserved"] - aggregate["unavailable"]
    )
    balances = list(queryset[:row_limit])
    rows = [
        [
            balance.warehouse.name,
            balance.warehouse.code,
            balance.book_edition.book.title,
            balance.book_edition.edition_code,
            balance.book_edition.language,
            balance.on_hand_quantity,
            balance.reserved_quantity,
            balance.unavailable_quantity,
            balance.available_quantity,
        ]
        for balance in balances
    ]
    return _result(
        "current_inventory",
        filters,
        columns=(
            _column("Warehouse"), _column("Code"), _column("Book"),
            _column("Edition"), _column("Language"),
            _column("On hand", numeric=True), _column("Reserved", numeric=True),
            _column("Unavailable", numeric=True), _column("Available", numeric=True),
        ),
        rows=rows,
        totals=(
            {"label": "Editions", "value": total_count},
            {"label": "On hand", "value": aggregate["on_hand"]},
            {"label": "Reserved", "value": aggregate["reserved"]},
            {"label": "Unavailable", "value": aggregate["unavailable"]},
            {"label": "Available", "value": aggregate["available"]},
        ),
        truncated=total_count > row_limit,
    )


def _stock_activity(filters, warehouse_ids, row_limit):
    queryset = StockMovement.objects.filter(
        warehouse_id__in=warehouse_ids,
        performed_at__date__lte=filters["date_to"],
    )
    queryset = _scope_warehouse(queryset, filters)
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(book_edition__book__title__icontains=query)
            | Q(book_edition__edition_code__icontains=query)
            | Q(book_edition__isbn__icontains=query)
            | Q(book_edition__barcode__icontains=query)
        )

    opening_in = Q(
        performed_at__date__lt=filters["date_from"],
        movement_type__in=STOCK_IN_TYPES,
    )
    opening_out = Q(
        performed_at__date__lt=filters["date_from"],
        movement_type__in=STOCK_OUT_TYPES,
    )
    period = Q(
        performed_at__date__gte=filters["date_from"],
        performed_at__date__lte=filters["date_to"],
    )
    grouped = queryset.values(
        "warehouse__name",
        "warehouse__code",
        "book_edition__book__title",
        "book_edition__edition_code",
        "book_edition__language",
    ).annotate(
        opening_in=Coalesce(Sum("quantity", filter=opening_in), Value(0)),
        opening_out=Coalesce(Sum("quantity", filter=opening_out), Value(0)),
        incoming=Coalesce(
            Sum("quantity", filter=period & Q(movement_type__in=STOCK_IN_TYPES)),
            Value(0),
        ),
        outgoing=Coalesce(
            Sum("quantity", filter=period & Q(movement_type__in=STOCK_OUT_TYPES)),
            Value(0),
        ),
    ).order_by(
        "warehouse__name", "book_edition__book__title", "book_edition__edition_code"
    )
    total_count = grouped.count()
    aggregate = queryset.aggregate(
        opening_in=Coalesce(Sum("quantity", filter=opening_in), Value(0)),
        opening_out=Coalesce(Sum("quantity", filter=opening_out), Value(0)),
        incoming=Coalesce(
            Sum("quantity", filter=period & Q(movement_type__in=STOCK_IN_TYPES)),
            Value(0),
        ),
        outgoing=Coalesce(
            Sum("quantity", filter=period & Q(movement_type__in=STOCK_OUT_TYPES)),
            Value(0),
        ),
    )
    aggregate["opening"] = aggregate["opening_in"] - aggregate["opening_out"]
    aggregate["net"] = aggregate["incoming"] - aggregate["outgoing"]
    aggregate["closing"] = aggregate["opening"] + aggregate["net"]
    rows = []
    for item in grouped[:row_limit]:
        opening = item["opening_in"] - item["opening_out"]
        net = item["incoming"] - item["outgoing"]
        rows.append([
            item["warehouse__name"], item["warehouse__code"],
            item["book_edition__book__title"], item["book_edition__edition_code"],
            item["book_edition__language"], opening, item["incoming"],
            item["outgoing"], net, opening + net,
        ])
    return _result(
        "stock_activity",
        filters,
        columns=(
            _column("Warehouse"), _column("Code"), _column("Book"),
            _column("Edition"), _column("Language"),
            _column("Opening", numeric=True), _column("Incoming", numeric=True),
            _column("Outgoing", numeric=True), _column("Net", numeric=True),
            _column("Closing", numeric=True),
        ),
        rows=rows,
        totals=(
            {"label": "Edition rows", "value": total_count},
            {"label": "Opening", "value": aggregate["opening"]},
            {"label": "Incoming", "value": aggregate["incoming"]},
            {"label": "Outgoing", "value": aggregate["outgoing"]},
            {"label": "Net", "value": aggregate["net"]},
            {"label": "Closing", "value": aggregate["closing"]},
        ),
        truncated=total_count > row_limit,
    )


def _movement_detail(filters, warehouse_ids, row_limit):
    queryset = StockMovement.objects.filter(
        warehouse_id__in=warehouse_ids
    ).select_related(
        "warehouse", "location", "book_edition__book", "lot", "performed_by"
    )
    queryset = _scope_warehouse(queryset, filters)
    queryset = _date_scope(queryset, filters, "performed_at")
    if filters["movement_type"]:
        queryset = queryset.filter(movement_type=filters["movement_type"])
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(book_edition__book__title__icontains=query)
            | Q(book_edition__edition_code__icontains=query)
            | Q(lot__lot_number__icontains=query)
            | Q(reference_type__icontains=query)
            | Q(reference_id__icontains=query)
            | Q(notes__icontains=query)
        )
    total_count = queryset.count()
    quantity_aggregate = queryset.aggregate(
        incoming=Coalesce(
            Sum("quantity", filter=Q(movement_type__in=STOCK_IN_TYPES)),
            Value(0),
        ),
        outgoing=Coalesce(
            Sum("quantity", filter=Q(movement_type__in=STOCK_OUT_TYPES)),
            Value(0),
        ),
    )
    movements = list(queryset.order_by("-performed_at", "-pk")[:row_limit])
    rows = [
        [
            movement.performed_at,
            movement.warehouse.name,
            str(movement.location or "—"),
            movement.book_edition.book.title,
            movement.book_edition.edition_code,
            movement.get_movement_type_display(),
            movement.signed_quantity,
            movement.lot.lot_number if movement.lot_id else "—",
            f"{movement.reference_type}: {movement.reference_id}".strip(": ") or "—",
            str(movement.performed_by or "System"),
        ]
        for movement in movements
    ]
    return _result(
        "movement_detail",
        filters,
        columns=(
            _column("Date/time"), _column("Warehouse"), _column("Location"),
            _column("Book"), _column("Edition"), _column("Movement"),
            _column("Signed quantity", numeric=True), _column("Lot"),
            _column("Reference"), _column("Performed by"),
        ),
        rows=rows,
        totals=(
            {"label": "Movements", "value": total_count},
            {
                "label": "Net quantity",
                "value": quantity_aggregate["incoming"] - quantity_aggregate["outgoing"],
            },
        ),
        truncated=total_count > row_limit,
    )


def _inbound(filters, warehouse_ids, row_limit):
    queryset = InboundShipment.objects.filter(
        warehouse_id__in=warehouse_ids
    ).select_related("warehouse", "supplier", "donor", "stock_posted_by")
    queryset = _scope_warehouse(queryset, filters)
    queryset = _date_scope(queryset, filters, "received_at")
    if filters["currency"]:
        queryset = queryset.filter(currency=filters["currency"])
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(shipment_number__icontains=query)
            | Q(supplier_name__icontains=query)
            | Q(donor_name__icontains=query)
            | Q(invoice_reference__icontains=query)
            | Q(notes__icontains=query)
        )
    total_count = queryset.count()
    shipments = list(queryset.order_by("-received_at", "-pk")[:row_limit])
    currency_groups = defaultdict(lambda: {
        "total": Decimal("0.00"), "paid": Decimal("0.00"), "remaining": Decimal("0.00")
    })
    rows = []
    for shipment in shipments:
        group = currency_groups[shipment.currency]
        group["total"] += shipment.total_cost
        group["paid"] += shipment.amount_paid
        group["remaining"] += shipment.amount_due
        party = shipment.supplier_name or shipment.donor_name or "—"
        rows.append([
            shipment.received_at,
            shipment.shipment_number,
            shipment.warehouse.name,
            shipment.get_source_type_display(),
            party,
            "Posted" if shipment.is_stock_posted else "Draft",
            shipment.total_cost,
            shipment.amount_paid,
            shipment.amount_due,
            shipment.currency,
            shipment.get_payment_status_display(),
        ])
    return _result(
        "inbound",
        filters,
        columns=(
            _column("Received"), _column("Shipment"), _column("Warehouse"),
            _column("Source"), _column("Supplier / donor"), _column("Stock"),
            _column("Total cost", numeric=True), _column("Paid", numeric=True),
            _column("Due", numeric=True), _column("Currency"), _column("Payment"),
        ),
        rows=rows,
        totals=({"label": "Shipments", "value": total_count},),
        currency_totals=_currency_cards(currency_groups),
        truncated=total_count > row_limit,
    )


def _orders(filters, warehouse_ids, row_limit):
    scoped_items = BookOrderItem.objects.filter(
        warehouse_id__in=warehouse_ids
    ).select_related("warehouse")
    queryset = BookOrder.objects.filter(
        items__warehouse_id__in=warehouse_ids
    ).select_related("recipient_organization", "fulfilled_by").prefetch_related(
        Prefetch("items", queryset=scoped_items, to_attr="report_items")
    ).distinct()
    if filters["warehouse_id"]:
        queryset = queryset.filter(items__warehouse_id=filters["warehouse_id"])
    queryset = _date_scope(queryset, filters, "created_at")
    if filters["currency"]:
        queryset = queryset.filter(currency=filters["currency"])
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(order_number__icontains=query)
            | Q(recipient_first_name__icontains=query)
            | Q(recipient_last_name__icontains=query)
            | Q(organization_name__icontains=query)
            | Q(recipient_email__icontains=query)
            | Q(notes__icontains=query)
        )
    total_count = queryset.count()
    orders = list(queryset.order_by("-created_at", "-pk")[:row_limit])
    currency_groups = defaultdict(lambda: {
        "total": Decimal("0.00"), "paid": Decimal("0.00"), "remaining": Decimal("0.00")
    })
    rows = []
    for order in orders:
        group = currency_groups[order.currency]
        group["total"] += order.total_amount
        group["paid"] += order.paid_amount
        group["remaining"] += order.remaining_amount
        warehouse_names = ", ".join(sorted({
            item.warehouse.code
            for item in order.report_items
            if not filters["warehouse_id"] or item.warehouse_id == filters["warehouse_id"]
        })) or "—"
        rows.append([
            order.created_at,
            order.order_number,
            warehouse_names,
            order.recipient_display,
            order.get_order_type_display(),
            order.get_purpose_display(),
            order.get_status_display(),
            order.total_amount,
            order.paid_amount,
            order.remaining_amount,
            order.currency,
        ])
    return _result(
        "orders",
        filters,
        columns=(
            _column("Created"), _column("Order"), _column("Warehouse(s)"),
            _column("Recipient"), _column("Type"), _column("Purpose"),
            _column("Status"), _column("Total", numeric=True),
            _column("Paid", numeric=True), _column("Remaining", numeric=True),
            _column("Currency"),
        ),
        rows=rows,
        totals=({"label": "Orders", "value": total_count},),
        currency_totals=_currency_cards(currency_groups),
        truncated=total_count > row_limit,
    )


def _transfers(filters, warehouse_ids, row_limit):
    queryset = StockTransfer.objects.filter(
        Q(from_warehouse_id__in=warehouse_ids) | Q(to_warehouse_id__in=warehouse_ids)
    ).select_related("from_warehouse", "to_warehouse", "dispatched_by", "received_by")
    if filters["warehouse_id"]:
        queryset = queryset.filter(
            Q(from_warehouse_id=filters["warehouse_id"])
            | Q(to_warehouse_id=filters["warehouse_id"])
        )
    queryset = _date_scope(queryset, filters, "created_at")
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(transfer_number__icontains=query)
            | Q(from_warehouse__name__icontains=query)
            | Q(to_warehouse__name__icontains=query)
            | Q(notes__icontains=query)
        )
    queryset = queryset.annotate(
        dispatched_quantity=Coalesce(Sum("items__quantity"), Value(0)),
        received_quantity_total=Coalesce(Sum("items__received_quantity"), Value(0)),
    )
    total_count = queryset.count()
    transfers = list(queryset.order_by("-created_at", "-pk")[:row_limit])
    rows = [
        [
            transfer.created_at,
            transfer.transfer_number,
            transfer.from_warehouse.name,
            transfer.to_warehouse.name,
            transfer.get_status_display(),
            transfer.dispatched_quantity,
            transfer.received_quantity_total,
            transfer.dispatched_at or "—",
            transfer.received_at or "—",
        ]
        for transfer in transfers
    ]
    return _result(
        "transfers",
        filters,
        columns=(
            _column("Created"), _column("Transfer"), _column("From"),
            _column("To"), _column("Status"),
            _column("Dispatched qty", numeric=True), _column("Received qty", numeric=True),
            _column("Dispatched at"), _column("Received at"),
        ),
        rows=rows,
        totals=(
            {"label": "Transfers", "value": total_count},
            {"label": "Dispatched quantity", "value": sum(row[5] for row in rows)},
            {"label": "Received quantity", "value": sum(row[6] for row in rows)},
        ),
        truncated=total_count > row_limit,
    )


def _supplier_payables(filters, warehouse_ids, row_limit):
    queryset = InboundPaymentSchedule.objects.filter(
        shipment__warehouse_id__in=warehouse_ids
    ).select_related("shipment__warehouse", "shipment__supplier").prefetch_related("payments")
    queryset = _scope_warehouse(queryset, filters, "shipment__warehouse_id")
    if filters["date_from"]:
        queryset = queryset.filter(due_date__gte=filters["date_from"])
    if filters["date_to"]:
        queryset = queryset.filter(due_date__lte=filters["date_to"])
    if filters["currency"]:
        queryset = queryset.filter(currency=filters["currency"])
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(shipment__shipment_number__icontains=query)
            | Q(shipment__supplier_name__icontains=query)
            | Q(description__icontains=query)
            | Q(notes__icontains=query)
        )
    total_count = queryset.count()
    schedules = list(queryset.order_by("due_date", "pk")[:row_limit])
    currency_groups = defaultdict(lambda: {
        "total": Decimal("0.00"), "paid": Decimal("0.00"), "remaining": Decimal("0.00")
    })
    rows = []
    for schedule in schedules:
        paid = schedule.paid_amount
        remaining = schedule.remaining_amount
        group = currency_groups[schedule.currency]
        group["total"] += schedule.amount
        group["paid"] += paid
        group["remaining"] += remaining
        rows.append([
            schedule.due_date,
            schedule.shipment.shipment_number,
            schedule.shipment.warehouse.name,
            schedule.shipment.supplier_name or "—",
            schedule.description or "—",
            schedule.amount,
            paid,
            remaining,
            schedule.currency,
            "Overdue" if schedule.is_overdue else schedule.get_status_display(),
        ])
    return _result(
        "supplier_payables",
        filters,
        columns=(
            _column("Due date"), _column("Shipment"), _column("Warehouse"),
            _column("Supplier"), _column("Instalment"),
            _column("Scheduled", numeric=True), _column("Paid", numeric=True),
            _column("Remaining", numeric=True), _column("Currency"), _column("Status"),
        ),
        rows=rows,
        totals=({"label": "Instalments", "value": total_count},),
        currency_totals=_currency_cards(currency_groups),
        truncated=total_count > row_limit,
    )


def scoped_cash_ledger_queryset(user, warehouse_ids=None):
    """Scope ledger rows through their source payment and warehouse.

    Manual ledger rows have no warehouse relationship and therefore remain
    superuser-only until a future model explicitly assigns them to a warehouse.
    """

    queryset = CashLedgerEntry.objects.all()
    if getattr(user, "is_superuser", False):
        return queryset

    warehouse_ids = (
        list(warehouse_ids)
        if warehouse_ids is not None
        else report_warehouse_ids(user)
    )

    order_payment_ids = PaymentRecord.objects.filter(
        order__items__warehouse_id__in=warehouse_ids
    ).values_list("pk", flat=True).distinct()
    inbound_payment_ids = InboundPayment.objects.filter(
        shipment__warehouse_id__in=warehouse_ids
    ).values_list("pk", flat=True).distinct()
    return queryset.filter(
        Q(reference_type="order_payment", reference_id__in=[str(pk) for pk in order_payment_ids])
        | Q(reference_type="inbound_payment", reference_id__in=[str(pk) for pk in inbound_payment_ids])
    )


def _cash_ledger(user, filters, warehouse_ids, row_limit):
    queryset = scoped_cash_ledger_queryset(user, warehouse_ids).select_related("recorded_by")
    queryset = _date_scope(queryset, filters, "entry_date")
    if filters["currency"]:
        queryset = queryset.filter(currency=filters["currency"])
    if filters["query"]:
        query = filters["query"]
        queryset = queryset.filter(
            Q(reference_type__icontains=query)
            | Q(reference_id__icontains=query)
            | Q(notes__icontains=query)
        )
    total_count = queryset.count()
    entries = list(queryset.order_by("-entry_date", "-pk")[:row_limit])
    currency_groups = defaultdict(lambda: {
        "cash_in": Decimal("0.00"), "cash_out": Decimal("0.00"), "net": Decimal("0.00")
    })
    rows = []
    for entry in entries:
        group = currency_groups[entry.currency]
        signed = entry.amount if entry.direction == CashEntryDirection.IN else -entry.amount
        if entry.direction == CashEntryDirection.IN:
            group["cash_in"] += entry.amount
        else:
            group["cash_out"] += entry.amount
        group["net"] += signed
        rows.append([
            entry.entry_date,
            entry.get_direction_display(),
            entry.get_entry_type_display(),
            signed,
            entry.currency,
            f"{entry.reference_type}: {entry.reference_id}".strip(": ") or "—",
            str(entry.recorded_by or "System"),
            entry.notes or "—",
        ])
    return _result(
        "cash_ledger",
        filters,
        columns=(
            _column("Date/time"), _column("Direction"), _column("Type"),
            _column("Signed amount", numeric=True), _column("Currency"),
            _column("Reference"), _column("Recorded by"), _column("Notes"),
        ),
        rows=rows,
        totals=({"label": "Ledger entries", "value": total_count},),
        currency_totals=_currency_cards(currency_groups),
        truncated=total_count > row_limit,
    )


REPORT_BUILDERS = {
    "current_inventory": _current_inventory,
    "stock_activity": _stock_activity,
    "movement_detail": _movement_detail,
    "inbound": _inbound,
    "orders": _orders,
    "transfers": _transfers,
    "supplier_payables": _supplier_payables,
}


def build_report(*, user, params, row_limit=None):
    available = available_report_definitions(user)
    if not available:
        raise ReportValidationError("You do not have permission to view bookstore reports.")
    allowed_codes = {definition["code"] for definition in available}
    code = str(params.get("report") or available[0]["code"])
    if code not in allowed_codes:
        raise ReportValidationError("You do not have permission to view that report.")

    warehouse_ids = report_warehouse_ids(user)
    filters = _filters(params, code=code, warehouse_ids=warehouse_ids)
    resolved_limit = int(
        row_limit
        or getattr(settings, "BOOKSTORE_ADMIN_REPORT_ROW_LIMIT", 2000)
    )
    resolved_limit = max(1, min(resolved_limit, 100000))
    if code == "cash_ledger":
        return _cash_ledger(user, filters, warehouse_ids, resolved_limit)
    return REPORT_BUILDERS[code](filters, warehouse_ids, resolved_limit)
