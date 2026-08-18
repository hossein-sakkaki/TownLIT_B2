# apps/bookstore_inventory/admin/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

import csv
import logging
from datetime import date, datetime
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    InboundPaymentScheduleStatus,
    OrderStatus,
    StockMovementType,
    TransferStatus,
)
from apps.bookstore_inventory.models import (
    Book,
    BookEdition,
    BookOrder,
    BookstoreWorkspace,
    CashLedgerEntry,
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
)
from apps.bookstore_inventory.services.access import current_warehouse_ids
from apps.bookstore_inventory.services.reports import (
    ReportValidationError,
    available_report_definitions,
    build_report,
    report_warehouses,
)


logger = logging.getLogger(__name__)


@admin.register(BookstoreWorkspace)
class BookstoreWorkspaceAdmin(admin.ModelAdmin):
    """A permission-aware home screen for every bookstore workflow."""

    change_list_template = "admin/bookstore_inventory/workspace.html"
    report_template = "admin/bookstore_inventory/reports.html"

    def get_urls(self):
        custom_urls = (
            path(
                "reports/",
                self.admin_site.admin_view(self.reports_view),
                name="bookstore_inventory_reports",
            ),
            path(
                "reports/export.csv",
                self.admin_site.admin_view(self.reports_csv_view),
                name="bookstore_inventory_reports_csv",
            ),
        )
        return list(custom_urls) + super().get_urls()

    def has_module_permission(self, request):
        return bool(
            request.user.is_active
            and request.user.is_staff
            and (
                request.user.is_superuser
                or request.user.has_module_perms("bookstore_inventory")
            )
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
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
        model_admin = self.admin_site._registry.get(model)
        if model_admin is None or not model_admin.has_view_permission(request):
            return None

        opts = model._meta
        link = {
            "label": label,
            "description": description,
            "url": reverse(
                f"admin:{opts.app_label}_{opts.model_name}_changelist",
                current_app=self.admin_site.name,
            ),
        }
        if add_label and model_admin.has_add_permission(request):
            link["add_label"] = add_label
            link["add_url"] = reverse(
                f"admin:{opts.app_label}_{opts.model_name}_add",
                current_app=self.admin_site.name,
            )
        return link

    def _can_view(self, request, model):
        model_admin = self.admin_site._registry.get(model)
        return bool(
            model_admin
            and model_admin.has_view_permission(request)
        )

    def _group(self, title, description, links):
        available_links = [link for link in links if link]
        if not available_links:
            return None
        return {
            "title": title,
            "description": description,
            "links": available_links,
        }

    def _reports_link(self, request):
        if not available_report_definitions(request.user):
            return None
        return {
            "label": "Reports centre",
            "description": (
                "Filter by warehouse and date, review operational totals, export CSV, "
                "or print a PDF-ready report."
            ),
            "url": reverse(
                "admin:bookstore_inventory_reports",
                current_app=self.admin_site.name,
            ),
        }

    def _warehouse_ids(self, request):
        if request.user.is_superuser:
            return list(Warehouse.objects.values_list("pk", flat=True))
        return list(current_warehouse_ids(request.user))

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            raise PermissionDenied

        warehouse_ids = self._warehouse_ids(request)
        balances = InventoryBalance.objects.filter(warehouse_id__in=warehouse_ids)
        stock = balances.aggregate(
            on_hand=Coalesce(Sum("on_hand_quantity"), 0),
            reserved=Coalesce(Sum("reserved_quantity"), 0),
            unavailable=Coalesce(Sum("unavailable_quantity"), 0),
        )
        stock["available"] = (
            stock["on_hand"] - stock["reserved"] - stock["unavailable"]
        )

        stats = [
            {
                "label": "My warehouses",
                "value": len(warehouse_ids),
                "tone": "neutral",
            },
        ]
        if self._can_view(request, InventoryBalance):
            stats.append({
                "label": "Available books",
                "value": stock["available"],
                "tone": "success" if stock["available"] > 0 else "warning",
            })
        if self._can_view(request, InboundShipment):
            stats.append({
                "label": "Inbound awaiting posting",
                "value": InboundShipment.objects.filter(
                    warehouse_id__in=warehouse_ids,
                    stock_posted_at__isnull=True,
                ).count(),
                "tone": "warning",
            })
        if self._can_view(request, BookOrder):
            stats.append({
                "label": "Open orders",
                "value": BookOrder.objects.filter(
                    items__warehouse_id__in=warehouse_ids,
                    status__in=(OrderStatus.DRAFT, OrderStatus.CONFIRMED),
                ).distinct().count(),
                "tone": "warning",
            })
        if self._can_view(request, StockTransfer):
            stats.append({
                "label": "Transfers in transit",
                "value": StockTransfer.objects.filter(
                    Q(from_warehouse_id__in=warehouse_ids)
                    | Q(to_warehouse_id__in=warehouse_ids),
                    status=TransferStatus.DISPATCHED,
                ).count(),
                "tone": "warning",
            })
        if self._can_view(request, InboundPaymentSchedule):
            stats.append({
                "label": "Overdue supplier payments",
                "value": InboundPaymentSchedule.objects.filter(
                    shipment__warehouse_id__in=warehouse_ids,
                    due_date__lt=timezone.localdate(),
                ).exclude(
                    status=InboundPaymentScheduleStatus.PAID,
                ).count(),
                "tone": "danger",
            })

        groups = (
            self._group(
                "1. Receive inventory",
                "Register incoming books, costs, due dates, and post verified stock.",
                (
                    self._model_link(
                        request,
                        InboundShipment,
                        label="Inbound shipments",
                        description="Receive donated, purchased, consigned, or returned books.",
                        add_label="New inbound shipment",
                    ),
                    self._model_link(
                        request,
                        InboundPaymentSchedule,
                        label="Supplier payment plan",
                        description="Review upcoming and overdue supplier installments.",
                    ),
                ),
            ),
            self._group(
                "2. Stock on hand",
                "See the current quantity available in each warehouse.",
                (
                    self._model_link(
                        request,
                        InventoryBalance,
                        label="Inventory balances",
                        description="The operational stock screen by edition and warehouse.",
                    ),
                ),
            ),
            self._group(
                "3. Orders and distribution",
                "Sell, donate, or distribute books from an assigned warehouse.",
                (
                    self._model_link(
                        request,
                        BookOrder,
                        label="Orders and distributions",
                        description="Create, reserve, and fulfil outgoing book orders.",
                        add_label="New order or distribution",
                    ),
                ),
            ),
            self._group(
                "4. Move stock",
                "Transfer books between TownLIT warehouses with dispatch and receipt control.",
                (
                    self._model_link(
                        request,
                        StockTransfer,
                        label="Warehouse transfers",
                        description="Dispatch from one warehouse and receive at another.",
                        add_label="New transfer",
                    ),
                ),
            ),
            self._group(
                "5. Count and correct",
                "Use controlled documents for counts, corrections, damage, loss, and returns.",
                (
                    self._model_link(
                        request,
                        StockCount,
                        label="Stock counts",
                        description="Capture expected quantities and post counted variances.",
                        add_label="New stock count",
                    ),
                    self._model_link(
                        request,
                        StockAdjustment,
                        label="Stock adjustments",
                        description="Controlled corrections for damage, loss, found stock, or data fixes.",
                        add_label="New adjustment",
                    ),
                    self._model_link(
                        request,
                        StockReturn,
                        label="Returns",
                        description="Record customer returns or books returned to a supplier.",
                        add_label="New return",
                    ),
                ),
            ),
            self._group(
                "6. Setup",
                "Maintain reusable master data instead of typing the same information again.",
                (
                    self._model_link(
                        request,
                        Warehouse,
                        label="Warehouses and staff",
                        description="Addresses, internal locations, and CustomUser assignments.",
                        add_label="New warehouse",
                    ),
                    self._model_link(
                        request,
                        OrganizationRecord,
                        label="Organizations",
                        description="Publishers, printers, suppliers, donors, and recipients.",
                        add_label="New organization",
                    ),
                    self._model_link(
                        request,
                        Book,
                        label="Books",
                        description="Shared title-level catalogue records.",
                        add_label="New book",
                    ),
                    self._model_link(
                        request,
                        BookEdition,
                        label="Book editions",
                        description="Physical variants, covers, language, format, and price.",
                        add_label="New edition",
                    ),
                ),
            ),
            self._group(
                "7. Finance and audit",
                "Review payments and immutable operational history.",
                (
                    self._model_link(
                        request,
                        CashLedgerEntry,
                        label="Cash ledger",
                        description="Cash in and out synchronized from bookstore payments.",
                    ),
                    self._model_link(
                        request,
                        PaymentRecord,
                        label="Customer payments",
                        description="Payments received against orders.",
                    ),
                    self._model_link(
                        request,
                        StockMovement,
                        label="Stock movement audit",
                        description="Immutable history of every stock change.",
                    ),
                ),
            ),
            self._group(
                "8. Reports and daily summary",
                "Operational reporting and the manager-facing morning inventory email.",
                (
                    self._reports_link(request),
                ),
            ),
        )

        technical_links = (
            self._model_link(
                request,
                InventoryLot,
                label="Inventory lots",
                description="Source and location traceability for received stock.",
            ),
            self._model_link(
                request,
                StockReservation,
                label="Reservations",
                description="Stock held for confirmed orders.",
            ),
            self._model_link(
                request,
                OrganizationProfileLink,
                label="Organization profile links",
                description="Future verified links to public organization profiles.",
            ),
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Bookstore workspace",
            "stats": stats,
            "workflow_groups": [group for group in groups if group],
            "technical_links": [link for link in technical_links if link],
            **(extra_context or {}),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            self.change_list_template,
            context,
        )

    def _can_queue_daily_report(self, request):
        return bool(
            request.user.is_superuser
            or request.user.has_perm(
                "bookstore_inventory.change_warehousestaffassignment"
            )
        )

    def _report_context(self, request, result=None, error=""):
        query = request.GET.copy()
        export_url = reverse(
            "admin:bookstore_inventory_reports_csv",
            current_app=self.admin_site.name,
        )
        if query:
            export_url = f"{export_url}?{query.urlencode()}"
        daily_schedule = {
            "configured": False,
            "enabled": False,
            "description": "Run the configuration command to create the morning schedule.",
        }
        try:
            from django_celery_beat.models import PeriodicTask

            periodic_task = PeriodicTask.objects.select_related("crontab").filter(
                name="TownLIT daily bookstore inventory summary"
            ).first()
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

            daily_recipient_count = len(daily_report_recipients())
        except Exception:
            logger.exception("bookstore.admin.daily_report_recipient_count_failed")
            daily_recipient_count = 0

        return {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Bookstore reports centre",
            "report_definitions": available_report_definitions(request.user),
            "warehouses": report_warehouses(request.user),
            "movement_types": StockMovementType.choices,
            "result": result,
            "report_error": error,
            "export_url": export_url,
            "can_queue_daily_report": self._can_queue_daily_report(request),
            "daily_schedule": daily_schedule,
            "daily_recipient_count": daily_recipient_count,
        }

    def reports_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        if not available_report_definitions(request.user):
            raise PermissionDenied

        if request.method == "POST":
            if not self._can_queue_daily_report(request):
                raise PermissionDenied
            try:
                from apps.bookstore_inventory.tasks import send_daily_inventory_report

                async_result = send_daily_inventory_report.delay()
            except Exception:
                logger.exception("bookstore.admin.daily_report_queue_failed")
                self.message_user(
                    request,
                    "The daily inventory email could not be queued. Check the Celery broker and worker.",
                    level=messages.ERROR,
                )
            else:
                self.message_user(
                    request,
                    f"Daily inventory email queued successfully (task {async_result.id}).",
                    level=messages.SUCCESS,
                )
            return HttpResponseRedirect(request.path)

        result = None
        error = ""
        try:
            result = build_report(user=request.user, params=request.GET)
        except ReportValidationError as exc:
            error = str(exc)
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request,
            self.report_template,
            self._report_context(request, result=result, error=error),
        )

    @staticmethod
    def _csv_value(value):
        if value is None:
            return ""
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                value = timezone.localtime(value)
            return value.isoformat(sep=" ", timespec="seconds")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, (int, float, Decimal)):
            return value
        text = str(value)
        if text.startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    def reports_csv_view(self, request):
        if not self.has_view_permission(request):
            raise PermissionDenied
        try:
            result = build_report(
                user=request.user,
                params=request.GET,
                row_limit=getattr(
                    settings,
                    "BOOKSTORE_REPORT_CSV_ROW_LIMIT",
                    50000,
                ),
            )
        except ReportValidationError as exc:
            return HttpResponse(str(exc), status=400, content_type="text/plain")

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="{result["filename"]}"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([column["label"] for column in result["columns"]])
        for row in result["rows"]:
            writer.writerow([self._csv_value(value) for value in row])
        return response
