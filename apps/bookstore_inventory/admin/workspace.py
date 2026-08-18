# apps/bookstore_inventory/admin/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

import csv
import logging
import secrets
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlencode
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import (
    HttpResponse,
    HttpResponseRedirect,
)
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    DocumentStatus,
    InboundPaymentScheduleStatus,
    OrderStatus,
    StockCountStatus,
    StockMovementType,
    TransferStatus,
)
from apps.bookstore_inventory.models import (
    Book,
    BookEdition,
    BookOrder,
    BookstoreWorkspace,
    CashLedgerEntry,
    EditionPrice,
    InboundPayment,
    InboundPaymentSchedule,
    InboundShipment,
    InventoryBalance,
    InventoryLot,
    OrganizationProfileLink,
    OrganizationRecord,
    PaymentRecord,
    StockAdjustment,
    StockCount,
    StockMovement,
    StockReservation,
    StockReturn,
    StockTransfer,
    Warehouse,
    WarehouseLocation,
    WarehouseStaffAssignment,
)
from apps.bookstore_inventory.forms.quick_issue import (
    QuickIssueForm,
    QuickIssueItemFormSet,
)
from apps.bookstore_inventory.services.quick_issue import (
    create_and_post_quick_issue,
)
from apps.bookstore_inventory.services.access import (
    current_warehouse_ids,
)
from apps.bookstore_inventory.services.reports import (
    ReportValidationError,
    available_report_definitions,
    build_report,
    report_warehouses,
)


logger = logging.getLogger(__name__)


@admin.register(BookstoreWorkspace)
class BookstoreWorkspaceAdmin(admin.ModelAdmin):
    """
    Permission-aware operational home screen.

    Daily users get a guided workflow, while experienced administrators
    can open the complete model directory from Browse all records.
    """

    change_list_template = (
        "admin/bookstore_inventory/workspace.html"
    )
    report_template = (
        "admin/bookstore_inventory/reports.html"
    )
    all_records_template = (
        "admin/bookstore_inventory/all_records.html"
    )
    quick_issue_template = (
        "admin/bookstore_inventory/quick_issue.html"
    )

    def get_urls(self):
        custom_urls = (
            path(
                "quick-issue/",
                self.admin_site.admin_view(
                    self.quick_issue_view
                ),
                name=(
                    "bookstore_inventory_quick_issue"
                ),
            ),
            path(
                "reports/",
                self.admin_site.admin_view(
                    self.reports_view
                ),
                name=(
                    "bookstore_inventory_reports"
                ),
            ),
            path(
                "reports/export.csv",
                self.admin_site.admin_view(
                    self.reports_csv_view
                ),
                name=(
                    "bookstore_inventory_reports_csv"
                ),
            ),
            path(
                "all-records/",
                self.admin_site.admin_view(
                    self.all_records_view
                ),
                name=(
                    "bookstore_inventory_all_records"
                ),
            ),
        )

        return list(
            custom_urls
        ) + super().get_urls()

    def has_module_permission(self, request):
        return bool(
            request.user.is_active
            and request.user.is_staff
            and (
                request.user.is_superuser
                or request.user.has_module_perms(
                    "bookstore_inventory"
                )
            )
        )

    def has_view_permission(
        self,
        request,
        obj=None,
    ):
        return self.has_module_permission(
            request
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def _model_link(
        self,
        request,
        model,
        *,
        label,
        description,
        add_label="",
    ):
        model_admin = (
            self.admin_site._registry.get(
                model
            )
        )

        if (
            model_admin is None
            or not model_admin.has_view_permission(
                request
            )
        ):
            return None

        opts = model._meta

        link = {
            "label": label,
            "description": description,
            "url": reverse(
                (
                    f"admin:{opts.app_label}_"
                    f"{opts.model_name}_changelist"
                ),
                current_app=self.admin_site.name,
            ),
        }

        if (
            add_label
            and model_admin.has_add_permission(
                request
            )
        ):
            link["add_label"] = add_label
            link["add_url"] = reverse(
                (
                    f"admin:{opts.app_label}_"
                    f"{opts.model_name}_add"
                ),
                current_app=self.admin_site.name,
            )

        return link

    def _model_list_url(
        self,
        model,
        params=None,
    ):
        opts = model._meta

        url = reverse(
            (
                f"admin:{opts.app_label}_"
                f"{opts.model_name}_changelist"
            ),
            current_app=self.admin_site.name,
        )

        if params:
            url = (
                f"{url}?"
                f"{urlencode(params)}"
            )

        return url

    def _can_view(
        self,
        request,
        model,
    ):
        model_admin = (
            self.admin_site._registry.get(
                model
            )
        )

        return bool(
            model_admin
            and model_admin.has_view_permission(
                request
            )
        )

    def _group(
        self,
        title,
        description,
        links,
    ):
        available_links = [
            link
            for link in links
            if link
        ]

        if not available_links:
            return None

        return {
            "title": title,
            "description": description,
            "links": available_links,
        }

    def _reports_link(self, request):
        if not available_report_definitions(
            request.user
        ):
            return None

        return {
            "label": "Reports centre",
            "description": (
                "Filter by warehouse and date, review operational "
                "totals, export CSV, or print a PDF-ready report."
            ),
            "url": reverse(
                "admin:bookstore_inventory_reports",
                current_app=self.admin_site.name,
            ),
        }

    def _all_records_link(self):
        return reverse(
            "admin:bookstore_inventory_all_records",
            current_app=self.admin_site.name,
        )

    def _can_quick_issue(
        self,
        request,
    ):
        if request.user.is_superuser:
            return True

        return bool(
            request.user.has_perm(
                "bookstore_inventory.add_bookorder"
            )
            and request.user.has_perm(
                "bookstore_inventory.fulfill_bookorder"
            )
            and current_warehouse_ids(
                request.user
            )
        )


    def _quick_issue_link(
        self,
        request,
    ):
        if not self._can_quick_issue(
            request
        ):
            return None

        return {
            "label": "Issue books — quick",
            "description": (
                "Immediately give away or sell books "
                "without opening the full order form."
            ),
            "url": reverse(
                "admin:bookstore_inventory_quick_issue",
                current_app=self.admin_site.name,
            ),
        }


    def _quick_issue_warehouses(
        self,
        request,
    ):
        if request.user.is_superuser:
            return Warehouse.objects.filter(
                is_active=True
            ).order_by(
                "name",
                "pk",
            )

        return Warehouse.objects.filter(
            pk__in=current_warehouse_ids(
                request.user
            ),
            is_active=True,
        ).order_by(
            "name",
            "pk",
        )


    def _quick_issue_editions(
        self,
        request,
        warehouse_ids,
    ):
        return (
            BookEdition.objects.filter(
                is_active=True,
                balances__warehouse_id__in=warehouse_ids,
                balances__on_hand_quantity__gt=0,
            )
            .filter(
                Q(is_sellable=True)
                | Q(is_distributable=True)
            )
            .select_related(
                "book"
            )
            .distinct()
            .order_by(
                "book__title",
                "edition_code",
            )
        )
        
    def _warehouse_ids(self, request):
        if request.user.is_superuser:
            return list(
                Warehouse.objects.values_list(
                    "pk",
                    flat=True,
                )
            )

        return list(
            current_warehouse_ids(
                request.user
            )
        )

    def changelist_view(
        self,
        request,
        extra_context=None,
    ):
        if not self.has_view_permission(
            request
        ):
            raise PermissionDenied

        warehouse_ids = self._warehouse_ids(
            request
        )

        balances = InventoryBalance.objects.filter(
            warehouse_id__in=warehouse_ids
        )

        stock = balances.aggregate(
            on_hand=Coalesce(
                Sum("on_hand_quantity"),
                0,
            ),
            reserved=Coalesce(
                Sum("reserved_quantity"),
                0,
            ),
            unavailable=Coalesce(
                Sum("unavailable_quantity"),
                0,
            ),
        )

        stock["available"] = (
            stock["on_hand"]
            - stock["reserved"]
            - stock["unavailable"]
        )

        stats = [
            {
                "label": "My warehouses",
                "value": len(
                    warehouse_ids
                ),
                "tone": "neutral",
                "url": (
                    self._model_list_url(
                        Warehouse
                    )
                    if self._can_view(
                        request,
                        Warehouse,
                    )
                    else ""
                ),
            },
        ]

        action_queue = []

        if self._can_view(
            request,
            InventoryBalance,
        ):
            stats.append({
                "label": "Available books",
                "value": stock["available"],
                "tone": (
                    "success"
                    if stock["available"] > 0
                    else "warning"
                ),
                "url": self._model_list_url(
                    InventoryBalance
                ),
            })

        if self._can_view(
            request,
            InboundShipment,
        ):
            inbound_count = (
                InboundShipment.objects.filter(
                    warehouse_id__in=warehouse_ids,
                    stock_posted_at__isnull=True,
                ).count()
            )

            stats.append({
                "label": "Inbound awaiting posting",
                "value": inbound_count,
                "tone": "warning",
                "url": self._model_list_url(
                    InboundShipment,
                    {
                        "stock_posted_at__isnull": (
                            "True"
                        )
                    },
                ),
            })

            if inbound_count:
                action_queue.append({
                    "label": (
                        "Inbound shipments awaiting stock posting"
                    ),
                    "count": inbound_count,
                    "tone": "warning",
                    "url": self._model_list_url(
                        InboundShipment,
                        {
                            "stock_posted_at__isnull": (
                                "True"
                            )
                        },
                    ),
                })

        if self._can_view(
            request,
            BookOrder,
        ):
            open_orders = (
                BookOrder.objects.filter(
                    items__warehouse_id__in=warehouse_ids,
                    status__in=(
                        OrderStatus.DRAFT,
                        OrderStatus.CONFIRMED,
                    ),
                )
                .distinct()
                .count()
            )

            stats.append({
                "label": "Open orders",
                "value": open_orders,
                "tone": "warning",
                "url": self._model_list_url(
                    BookOrder
                ),
            })

            if open_orders:
                action_queue.append({
                    "label": (
                        "Orders waiting for reservation or fulfilment"
                    ),
                    "count": open_orders,
                    "tone": "warning",
                    "url": self._model_list_url(
                        BookOrder
                    ),
                })

        if self._can_view(
            request,
            StockTransfer,
        ):
            in_transit = (
                StockTransfer.objects.filter(
                    Q(
                        from_warehouse_id__in=warehouse_ids
                    )
                    | Q(
                        to_warehouse_id__in=warehouse_ids
                    ),
                    status=TransferStatus.DISPATCHED,
                ).count()
            )

            stats.append({
                "label": "Transfers in transit",
                "value": in_transit,
                "tone": "warning",
                "url": self._model_list_url(
                    StockTransfer,
                    {
                        "status__exact": (
                            TransferStatus.DISPATCHED
                        )
                    },
                ),
            })

            if in_transit:
                action_queue.append({
                    "label": (
                        "Dispatched transfers waiting for receipt"
                    ),
                    "count": in_transit,
                    "tone": "warning",
                    "url": self._model_list_url(
                        StockTransfer,
                        {
                            "status__exact": (
                                TransferStatus.DISPATCHED
                            )
                        },
                    ),
                })

        if self._can_view(
            request,
            InboundPaymentSchedule,
        ):
            overdue_payments = (
                InboundPaymentSchedule.objects.filter(
                    shipment__warehouse_id__in=warehouse_ids,
                    due_date__lt=timezone.localdate(),
                )
                .exclude(
                    status=(
                        InboundPaymentScheduleStatus.PAID
                    ),
                )
                .count()
            )

            stats.append({
                "label": "Overdue supplier payments",
                "value": overdue_payments,
                "tone": (
                    "danger"
                    if overdue_payments
                    else "success"
                ),
                "url": self._model_list_url(
                    InboundPaymentSchedule,
                    {
                        "due_state": "overdue"
                    },
                ),
            })

            if overdue_payments:
                action_queue.append({
                    "label": (
                        "Overdue supplier instalments"
                    ),
                    "count": overdue_payments,
                    "tone": "danger",
                    "url": self._model_list_url(
                        InboundPaymentSchedule,
                        {
                            "due_state": "overdue"
                        },
                    ),
                })

        groups = (
            self._group(
                "Quick actions",
                (
                    "Fast daily bookstore operations "
                    "without opening the full administrative forms."
                ),
                (
                    self._quick_issue_link(
                        request
                    ),
                ),
            ),
            self._group(
                "1. Receive inventory",
                (
                    "Register incoming books, costs, due dates, "
                    "and post verified stock."
                ),
                (
                    self._model_link(
                        request,
                        InboundShipment,
                        label="Inbound shipments",
                        description=(
                            "Receive donated, purchased, consigned, "
                            "or returned books."
                        ),
                        add_label=(
                            "New inbound shipment"
                        ),
                    ),
                    self._model_link(
                        request,
                        InboundPaymentSchedule,
                        label=(
                            "Supplier payment plan"
                        ),
                        description=(
                            "Review upcoming and overdue "
                            "supplier instalments."
                        ),
                    ),
                ),
            ),
            self._group(
                "2. Stock on hand",
                (
                    "See the current quantity available "
                    "in each warehouse."
                ),
                (
                    self._model_link(
                        request,
                        InventoryBalance,
                        label="Inventory balances",
                        description=(
                            "The operational stock screen "
                            "by edition and warehouse."
                        ),
                    ),
                ),
            ),
            self._group(
                "3. Orders and distribution",
                (
                    "Sell, donate, or distribute books "
                    "from an assigned warehouse."
                ),
                (
                    self._model_link(
                        request,
                        BookOrder,
                        label=(
                            "Orders and distributions"
                        ),
                        description=(
                            "Create, reserve, and fulfil "
                            "outgoing book orders."
                        ),
                        add_label=(
                            "New order or distribution"
                        ),
                    ),
                ),
            ),
            self._group(
                "4. Move stock",
                (
                    "Transfer books between TownLIT warehouses "
                    "with dispatch and receipt control."
                ),
                (
                    self._model_link(
                        request,
                        StockTransfer,
                        label=(
                            "Warehouse transfers"
                        ),
                        description=(
                            "Dispatch from one warehouse "
                            "and receive at another."
                        ),
                        add_label="New transfer",
                    ),
                ),
            ),
            self._group(
                "5. Count and correct",
                (
                    "Controlled documents for counts, corrections, "
                    "damage, loss, and returns."
                ),
                (
                    self._model_link(
                        request,
                        StockCount,
                        label="Stock counts",
                        description=(
                            "Capture expected quantities "
                            "and post counted variances."
                        ),
                        add_label="New stock count",
                    ),
                    self._model_link(
                        request,
                        StockAdjustment,
                        label="Stock adjustments",
                        description=(
                            "Controlled corrections for damage, "
                            "loss, found stock, or data fixes."
                        ),
                        add_label="New adjustment",
                    ),
                    self._model_link(
                        request,
                        StockReturn,
                        label="Returns",
                        description=(
                            "Record customer returns or books "
                            "returned to a supplier."
                        ),
                        add_label="New return",
                    ),
                ),
            ),
            self._group(
                "6. Setup",
                (
                    "Maintain reusable master data instead of "
                    "typing the same information repeatedly."
                ),
                (
                    self._model_link(
                        request,
                        Warehouse,
                        label="Warehouses and staff",
                        description=(
                            "Addresses, internal locations, "
                            "and CustomUser assignments."
                        ),
                        add_label="New warehouse",
                    ),
                    self._model_link(
                        request,
                        OrganizationRecord,
                        label="Organizations",
                        description=(
                            "Publishers, printers, suppliers, "
                            "donors, and recipients."
                        ),
                        add_label="New organization",
                    ),
                    self._model_link(
                        request,
                        Book,
                        label="Books",
                        description=(
                            "Shared title-level catalogue records."
                        ),
                        add_label="New book",
                    ),
                    self._model_link(
                        request,
                        BookEdition,
                        label="Book editions",
                        description=(
                            "Physical variants, covers, language, "
                            "format, and price."
                        ),
                        add_label="New edition",
                    ),
                ),
            ),
            self._group(
                "7. Finance and audit",
                (
                    "Review payments and immutable "
                    "operational history."
                ),
                (
                    self._model_link(
                        request,
                        CashLedgerEntry,
                        label="Cash ledger",
                        description=(
                            "Cash in and out synchronized "
                            "from bookstore payments."
                        ),
                    ),
                    self._model_link(
                        request,
                        PaymentRecord,
                        label="Customer payments",
                        description=(
                            "Payments received against orders."
                        ),
                    ),
                    self._model_link(
                        request,
                        StockMovement,
                        label=(
                            "Stock movement audit"
                        ),
                        description=(
                            "Immutable history of every stock change."
                        ),
                    ),
                ),
            ),
            self._group(
                "8. Reports and daily summary",
                (
                    "Operational reporting and the manager-facing "
                    "morning inventory email."
                ),
                (
                    self._reports_link(request),
                ),
            ),
        )

        context = {
            **self.admin_site.each_context(
                request
            ),
            "opts": self.model._meta,
            "title": "Bookstore workspace",
            "stats": stats,
            "action_queue": action_queue,
            "workflow_groups": [
                group
                for group in groups
                if group
            ],
            "all_records_url": (
                self._all_records_link()
            ),
            **(extra_context or {}),
        }

        request.current_app = (
            self.admin_site.name
        )

        return TemplateResponse(
            request,
            self.change_list_template,
            context,
        )

    def _all_records_groups(self, request):
        groups = (
            self._group(
                "Operational records",
                (
                    "Direct access to the full operational "
                    "lists behind the guided workflows."
                ),
                (
                    self._model_link(
                        request,
                        InboundShipment,
                        label="Inbound shipments",
                        description=(
                            "All inbound shipment records."
                        ),
                        add_label=(
                            "New inbound shipment"
                        ),
                    ),
                    self._model_link(
                        request,
                        InboundPaymentSchedule,
                        label=(
                            "Supplier payment schedules"
                        ),
                        description=(
                            "All scheduled supplier instalments."
                        ),
                    ),
                    self._model_link(
                        request,
                        InboundPayment,
                        label="Inbound payments",
                        description=(
                            "Recorded supplier payments."
                        ),
                    ),
                    self._model_link(
                        request,
                        BookOrder,
                        label="Orders",
                        description=(
                            "All accessible sales and distribution orders."
                        ),
                        add_label="New order",
                    ),
                    self._model_link(
                        request,
                        PaymentRecord,
                        label="Customer payments",
                        description=(
                            "Payment records attached to orders."
                        ),
                    ),
                    self._model_link(
                        request,
                        StockTransfer,
                        label="Stock transfers",
                        description=(
                            "All warehouse-to-warehouse transfers."
                        ),
                        add_label="New transfer",
                    ),
                    self._model_link(
                        request,
                        StockCount,
                        label="Stock counts",
                        description=(
                            "Physical inventory count documents."
                        ),
                        add_label="New stock count",
                    ),
                    self._model_link(
                        request,
                        StockAdjustment,
                        label="Stock adjustments",
                        description=(
                            "Damage, loss, found stock and corrections."
                        ),
                        add_label="New adjustment",
                    ),
                    self._model_link(
                        request,
                        StockReturn,
                        label="Stock returns",
                        description=(
                            "Customer and supplier return documents."
                        ),
                        add_label="New return",
                    ),
                ),
            ),
            self._group(
                "Master data",
                (
                    "Reusable setup and catalogue records."
                ),
                (
                    self._model_link(
                        request,
                        Warehouse,
                        label="Warehouses",
                        description=(
                            "Warehouse setup, addresses, staff and locations."
                        ),
                        add_label="New warehouse",
                    ),
                    self._model_link(
                        request,
                        WarehouseLocation,
                        label="Warehouse locations",
                        description=(
                            "Zones, aisles, shelves, bins and staging areas."
                        ),
                    ),
                    self._model_link(
                        request,
                        WarehouseStaffAssignment,
                        label="Staff assignments",
                        description=(
                            "Direct view of warehouse responsibility records."
                        ),
                    ),
                    self._model_link(
                        request,
                        OrganizationRecord,
                        label="Organizations",
                        description=(
                            "Publishers, printers, suppliers, donors "
                            "and recipients."
                        ),
                        add_label="New organization",
                    ),
                    self._model_link(
                        request,
                        Book,
                        label="Books",
                        description=(
                            "Title-level catalogue records."
                        ),
                        add_label="New book",
                    ),
                    self._model_link(
                        request,
                        BookEdition,
                        label="Book editions",
                        description=(
                            "Language, print, cover and pricing variants."
                        ),
                        add_label="New edition",
                    ),
                ),
            ),
            self._group(
                "Inventory and audit",
                (
                    "Read-only or technical records used for "
                    "traceability and reconciliation."
                ),
                (
                    self._model_link(
                        request,
                        InventoryBalance,
                        label="Inventory balances",
                        description=(
                            "Current inventory by warehouse and edition."
                        ),
                    ),
                    self._model_link(
                        request,
                        InventoryLot,
                        label="Inventory lots",
                        description=(
                            "Lot and source traceability."
                        ),
                    ),
                    self._model_link(
                        request,
                        StockReservation,
                        label="Reservations",
                        description=(
                            "Stock held for confirmed orders."
                        ),
                    ),
                    self._model_link(
                        request,
                        StockMovement,
                        label="Stock movements",
                        description=(
                            "Immutable stock movement audit."
                        ),
                    ),
                    self._model_link(
                        request,
                        EditionPrice,
                        label="Edition price history",
                        description=(
                            "Immutable historical edition pricing."
                        ),
                    ),
                    self._model_link(
                        request,
                        CashLedgerEntry,
                        label="Cash ledger",
                        description=(
                            "Bookstore cash ledger entries."
                        ),
                    ),
                    self._model_link(
                        request,
                        OrganizationProfileLink,
                        label=(
                            "Organization profile links"
                        ),
                        description=(
                            "Verified future public-profile bridges."
                        ),
                    ),
                ),
            ),
        )

        return [
            group
            for group in groups
            if group
        ]

    def all_records_view(self, request):
        if not self.has_view_permission(
            request
        ):
            raise PermissionDenied

        request.current_app = (
            self.admin_site.name
        )

        return TemplateResponse(
            request,
            self.all_records_template,
            {
                **self.admin_site.each_context(
                    request
                ),
                "opts": self.model._meta,
                "title": (
                    "Bookstore — all records"
                ),
                "record_groups": (
                    self._all_records_groups(
                        request
                    )
                ),
            },
        )

    def _can_queue_daily_report(
        self,
        request,
    ):
        return bool(
            request.user.is_superuser
            or request.user.has_perm(
                (
                    "bookstore_inventory."
                    "change_warehousestaffassignment"
                )
            )
        )

    def _report_context(
        self,
        request,
        result=None,
        error="",
    ):
        query = request.GET.copy()

        export_url = reverse(
            "admin:bookstore_inventory_reports_csv",
            current_app=self.admin_site.name,
        )

        if query:
            export_url = (
                f"{export_url}?"
                f"{query.urlencode()}"
            )

        daily_schedule = {
            "configured": False,
            "enabled": False,
            "description": (
                "Run the configuration command to create "
                "the morning schedule."
            ),
        }

        try:
            from django_celery_beat.models import (
                PeriodicTask,
            )

            periodic_task = (
                PeriodicTask.objects.select_related(
                    "crontab"
                )
                .filter(
                    name=(
                        "TownLIT daily bookstore "
                        "inventory summary"
                    )
                )
                .first()
            )

            if periodic_task:
                daily_schedule = {
                    "configured": True,
                    "enabled": getattr(
                        settings,
                        "BOOKSTORE_DAILY_REPORT_ENABLED",
                        True,
                    ),
                    "description": (
                        "Daily at "
                        f"{getattr(settings, 'BOOKSTORE_DAILY_REPORT_HOUR', 7):02d}:"
                        f"{getattr(settings, 'BOOKSTORE_DAILY_REPORT_MINUTE', 0):02d} "
                        f"{getattr(settings, 'CELERY_TIMEZONE', settings.TIME_ZONE)}"
                    ),
                }

        except Exception:
            pass

        try:
            from apps.bookstore_inventory.services.daily_reports import (
                daily_report_recipients,
            )

            daily_recipient_count = len(
                daily_report_recipients()
            )

        except Exception:
            logger.exception(
                "bookstore.admin."
                "daily_report_recipient_count_failed"
            )
            daily_recipient_count = 0

        return {
            **self.admin_site.each_context(
                request
            ),
            "opts": self.model._meta,
            "title": (
                "Bookstore reports centre"
            ),
            "report_definitions": (
                available_report_definitions(
                    request.user
                )
            ),
            "warehouses": report_warehouses(
                request.user
            ),
            "movement_types": (
                StockMovementType.choices
            ),
            "result": result,
            "report_error": error,
            "export_url": export_url,
            "can_queue_daily_report": (
                self._can_queue_daily_report(
                    request
                )
            ),
            "daily_schedule": daily_schedule,
            "daily_recipient_count": (
                daily_recipient_count
            ),
        }

    def reports_view(self, request):
        if not self.has_view_permission(
            request
        ):
            raise PermissionDenied

        if not available_report_definitions(
            request.user
        ):
            raise PermissionDenied

        if request.method == "POST":
            if not self._can_queue_daily_report(
                request
            ):
                raise PermissionDenied

            try:
                from apps.bookstore_inventory.tasks import (
                    send_daily_inventory_report,
                )

                async_result = (
                    send_daily_inventory_report.delay()
                )

            except Exception:
                logger.exception(
                    "bookstore.admin."
                    "daily_report_queue_failed"
                )
                self.message_user(
                    request,
                    (
                        "The daily inventory email could not be queued. "
                        "Check the Celery broker and worker."
                    ),
                    level=messages.ERROR,
                )

            else:
                self.message_user(
                    request,
                    (
                        "Daily inventory email queued successfully "
                        f"(task {async_result.id})."
                    ),
                    level=messages.SUCCESS,
                )

            return HttpResponseRedirect(
                request.path
            )

        result = None
        error = ""

        try:
            result = build_report(
                user=request.user,
                params=request.GET,
            )
        except ReportValidationError as exc:
            error = str(exc)

        request.current_app = (
            self.admin_site.name
        )

        return TemplateResponse(
            request,
            self.report_template,
            self._report_context(
                request,
                result=result,
                error=error,
            ),
        )

    def quick_issue_view(
        self,
        request,
    ):
        if not self._can_quick_issue(
            request
        ):
            raise PermissionDenied

        warehouses = (
            self._quick_issue_warehouses(
                request
            )
        )

        warehouse_ids = list(
            warehouses.values_list(
                "pk",
                flat=True,
            )
        )

        editions = (
            self._quick_issue_editions(
                request,
                warehouse_ids,
            )
        )

        organizations = (
            OrganizationRecord.objects.filter(
                is_active=True
            ).order_by(
                "display_name",
                "official_name",
                "pk",
            )
        )

        session_key = (
            "bookstore_quick_issue_submission_token"
        )

        if request.method == "POST":
            expected_token = (
                request.session.get(
                    session_key
                )
            )

            form = QuickIssueForm(
                request.POST,
                warehouse_queryset=warehouses,
                organization_queryset=organizations,
            )

            item_formset = QuickIssueItemFormSet(
                request.POST,
                prefix="items",
                form_kwargs={
                    "edition_queryset": editions,
                },
            )

            form_valid = form.is_valid()
            items_valid = (
                item_formset.is_valid()
            )

            if form_valid and items_valid:
                submitted_token = (
                    form.cleaned_data.get(
                        "submission_token"
                    )
                    or ""
                )

                if (
                    not expected_token
                    or not secrets.compare_digest(
                        submitted_token,
                        expected_token,
                    )
                ):
                    form.add_error(
                        None,
                        (
                            "This Quick Issue form has expired "
                            "or was already submitted. "
                            "Reload the page and try again."
                        ),
                    )

                else:
                    item_rows = [
                        item_form.cleaned_data
                        for item_form
                        in item_formset.forms
                        if (
                            hasattr(
                                item_form,
                                "cleaned_data",
                            )
                            and item_form.cleaned_data
                            and not item_form.cleaned_data.get(
                                "DELETE"
                            )
                            and item_form.cleaned_data.get(
                                "book_edition"
                            )
                        )
                    ]

                    try:
                        order = (
                            create_and_post_quick_issue(
                                user=request.user,
                                warehouse=(
                                    form.cleaned_data[
                                        "warehouse"
                                    ]
                                ),
                                issue_at=(
                                    form.cleaned_data[
                                        "issue_at"
                                    ]
                                ),
                                issue_type=(
                                    form.cleaned_data[
                                        "issue_type"
                                    ]
                                ),
                                purpose=(
                                    form.cleaned_data[
                                        "purpose"
                                    ]
                                ),
                                recipient_type=(
                                    form.cleaned_data[
                                        "recipient_type"
                                    ]
                                ),
                                recipient_name=(
                                    form.cleaned_data[
                                        "recipient_name"
                                    ]
                                ),
                                recipient_organization=(
                                    form.cleaned_data.get(
                                        "recipient_organization"
                                    )
                                ),
                                currency=(
                                    form.cleaned_data[
                                        "currency"
                                    ]
                                ),
                                payment_method=(
                                    form.cleaned_data.get(
                                        "payment_method"
                                    )
                                ),
                                transaction_reference=(
                                    form.cleaned_data.get(
                                        "transaction_reference"
                                    )
                                ),
                                notes=(
                                    form.cleaned_data.get(
                                        "notes"
                                    )
                                ),
                                items=item_rows,
                            )
                        )

                    except ValidationError as exc:
                        message = "; ".join(
                            exc.messages
                        )

                        form.add_error(
                            None,
                            message,
                        )

                    else:
                        request.session.pop(
                            session_key,
                            None,
                        )

                        self.message_user(
                            request,
                            (
                                f"Quick Issue {order.order_number} "
                                "was posted successfully."
                            ),
                            level=messages.SUCCESS,
                        )

                        return HttpResponseRedirect(
                            (
                                f"{request.path}"
                                f"?created={order.pk}"
                            )
                        )

        else:
            submission_token = (
                secrets.token_urlsafe(32)
            )

            request.session[
                session_key
            ] = submission_token

            form = QuickIssueForm(
                initial={
                    "submission_token": (
                        submission_token
                    ),
                    "issue_at": (
                        timezone.localtime()
                    ),
                    "issue_type": (
                        "free_distribution"
                    ),
                    "purpose": (
                        "church_support"
                    ),
                    "recipient_type": (
                        "organization"
                    ),
                    "currency": "CAD",
                    "payment_method": "cash",
                },
                warehouse_queryset=warehouses,
                organization_queryset=organizations,
            )

            item_formset = QuickIssueItemFormSet(
                prefix="items",
                form_kwargs={
                    "edition_queryset": editions,
                },
            )

        created_order_url = ""
        created_order_number = ""

        created_id = str(
            request.GET.get(
                "created"
            )
            or ""
        ).strip()

        if created_id:
            order_admin = (
                self.admin_site._registry.get(
                    BookOrder
                )
            )

            if order_admin:
                created_order = (
                    order_admin.get_queryset(
                        request
                    )
                    .filter(
                        pk=created_id
                    )
                    .first()
                )

                if created_order:
                    created_order_number = (
                        created_order.order_number
                    )

                    created_order_url = reverse(
                        (
                            "admin:"
                            "bookstore_inventory_"
                            "bookorder_change"
                        ),
                        args=[
                            created_order.pk
                        ],
                        current_app=(
                            self.admin_site.name
                        ),
                    )

        edition_price_map = {
            str(edition.pk): str(
                edition.fixed_price
                or Decimal("0.00")
            )
            for edition in editions
        }

        request.current_app = (
            self.admin_site.name
        )

        return TemplateResponse(
            request,
            self.quick_issue_template,
            {
                **self.admin_site.each_context(
                    request
                ),
                "opts": self.model._meta,
                "title": "Quick Issue",
                "form": form,
                "item_formset": item_formset,
                "edition_price_map": (
                    edition_price_map
                ),
                "created_order_url": (
                    created_order_url
                ),
                "created_order_number": (
                    created_order_number
                ),
            },
        )
        
    @staticmethod
    def _csv_value(value):
        if value is None:
            return ""

        if isinstance(
            value,
            datetime,
        ):
            if timezone.is_aware(value):
                value = timezone.localtime(
                    value
                )

            return value.isoformat(
                sep=" ",
                timespec="seconds",
            )

        if isinstance(value, date):
            return value.isoformat()

        if isinstance(
            value,
            (int, float, Decimal),
        ):
            return value

        text = str(value)

        if text.startswith(
            ("=", "+", "-", "@")
        ):
            return f"'{text}"

        return text

    def reports_csv_view(self, request):
        if not self.has_view_permission(
            request
        ):
            raise PermissionDenied

        try:
            result = build_report(
                user=request.user,
                params=request.GET,
                row_limit=getattr(
                    settings,
                    (
                        "BOOKSTORE_REPORT_"
                        "CSV_ROW_LIMIT"
                    ),
                    50000,
                ),
            )
        except ReportValidationError as exc:
            return HttpResponse(
                str(exc),
                status=400,
                content_type="text/plain",
            )

        response = HttpResponse(
            content_type=(
                "text/csv; charset=utf-8"
            )
        )
        response[
            "Content-Disposition"
        ] = (
            'attachment; '
            f'filename="{result["filename"]}"'
        )

        response.write("\ufeff")

        writer = csv.writer(response)

        writer.writerow([
            column["label"]
            for column in result["columns"]
        ])

        for row in result["rows"]:
            writer.writerow([
                self._csv_value(value)
                for value in row
            ])

        return response