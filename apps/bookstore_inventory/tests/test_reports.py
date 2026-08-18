# apps/bookstore_inventory/tests/test_reports.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    PricingMode,
    StockMovementType,
    WarehouseStaffRole,
)
from apps.bookstore_inventory.models import (
    Book,
    BookEdition,
    InventoryBalance,
    StockMovement,
    Warehouse,
    WarehouseStaffAssignment,
)
from apps.bookstore_inventory.services.daily_reports import (
    build_daily_inventory_snapshot,
    daily_report_recipients,
    send_daily_inventory_summary,
)
from apps.bookstore_inventory.services.reports import build_report


def create_user(*, email, username, superuser=False):
    user_model = get_user_model()
    user = user_model.objects.create_user(
        email=email,
        username=username,
        password="test-password",
    )
    user.is_active = True
    user.is_superuser = superuser
    concrete_fields = {field.name for field in user_model._meta.fields}
    if "is_admin" in concrete_fields:
        user.is_admin = superuser
    if "is_staff" in concrete_fields:
        user.is_staff = True
    user.save()
    return user


class BookstoreReportingTests(TestCase):
    def setUp(self):
        self.admin_user = create_user(
            email="report-admin@example.com",
            username="report-admin",
            superuser=True,
        )
        self.warehouse = Warehouse.objects.create(
            name="Central Office",
            code="YVR-HQ",
        )
        self.book = Book.objects.create(title="Persian Bible")
        self.edition = BookEdition.objects.create(
            book=self.book,
            edition_code="FA-NMV-GOLD",
            language="Persian",
            pricing_mode=PricingMode.FIXED_PRICE,
            fixed_price=Decimal("40.00"),
            currency="CAD",
        )
        now = timezone.now()
        StockMovement.objects.create(
            warehouse=self.warehouse,
            book_edition=self.edition,
            movement_type=StockMovementType.IN,
            quantity=10,
            performed_at=now - timedelta(days=40),
        )
        StockMovement.objects.create(
            warehouse=self.warehouse,
            book_edition=self.edition,
            movement_type=StockMovementType.SALE,
            quantity=2,
            performed_at=now - timedelta(days=2),
        )

    def test_stock_activity_has_opening_incoming_outgoing_and_closing(self):
        today = timezone.localdate()
        result = build_report(
            user=self.admin_user,
            params={
                "report": "stock_activity",
                "date_from": (today - timedelta(days=29)).isoformat(),
                "date_to": today.isoformat(),
            },
        )
        self.assertEqual(len(result["rows"]), 1)
        row = result["rows"][0]
        self.assertEqual(row[5], 10)
        self.assertEqual(row[6], 0)
        self.assertEqual(row[7], 2)
        self.assertEqual(row[8], -2)
        self.assertEqual(row[9], 8)

    def test_non_superuser_report_is_limited_to_assigned_warehouses(self):
        second = Warehouse.objects.create(name="North Vancouver", code="YVR-NV")
        StockMovement.objects.create(
            warehouse=second,
            book_edition=self.edition,
            movement_type=StockMovementType.IN,
            quantity=99,
            performed_at=timezone.now(),
        )
        manager = create_user(
            email="manager@example.com",
            username="manager",
        )
        manager.user_permissions.add(
            Permission.objects.get(codename="view_inventorybalance")
        )
        WarehouseStaffAssignment.objects.create(
            warehouse=self.warehouse,
            user=manager,
            role=WarehouseStaffRole.MANAGER,
        )

        result = build_report(
            user=manager,
            params={"report": "current_inventory"},
        )
        self.assertEqual({row[1] for row in result["rows"]}, {"YVR-HQ"})
        self.assertEqual(result["rows"][0][5], 8)

    def test_admin_reports_page_and_csv_export_are_available(self):
        self.client.force_login(self.admin_user)
        reports_url = reverse("admin:bookstore_inventory_reports")
        response = self.client.get(reports_url, {"report": "current_inventory"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Bookstore reports centre")
        self.assertContains(response, "Persian Bible")

        csv_url = reverse("admin:bookstore_inventory_reports_csv")
        response = self.client.get(csv_url, {"report": "current_inventory"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith("\ufeff".encode("utf-8")))
        self.assertIn(b"FA-NMV-GOLD", response.content)


class DailyInventoryEmailTests(TestCase):
    def setUp(self):
        self.central = Warehouse.objects.create(name="Central", code="YVR-HQ")
        self.north = Warehouse.objects.create(name="North", code="YVR-NV")
        self.manager = create_user(
            email="warehouse-manager@example.com",
            username="warehouse-manager",
        )
        self.operator = create_user(
            email="warehouse-operator@example.com",
            username="warehouse-operator",
        )
        WarehouseStaffAssignment.objects.create(
            warehouse=self.central,
            user=self.manager,
            role=WarehouseStaffRole.PRIMARY_MANAGER,
        )
        WarehouseStaffAssignment.objects.create(
            warehouse=self.north,
            user=self.manager,
            role=WarehouseStaffRole.MANAGER,
        )
        WarehouseStaffAssignment.objects.create(
            warehouse=self.central,
            user=self.operator,
            role=WarehouseStaffRole.OPERATOR,
        )
        book = Book.objects.create(title="Free Persian New Testament")
        edition = BookEdition.objects.create(
            book=book,
            edition_code="FA-NT-FREE",
            language="Persian",
            pricing_mode=PricingMode.FREE,
            fixed_price=Decimal("0.00"),
            currency="CAD",
        )
        InventoryBalance.objects.create(
            warehouse=self.central,
            book_edition=edition,
            on_hand_quantity=6,
            reserved_quantity=1,
            unavailable_quantity=0,
        )

    def test_manager_is_deduplicated_and_operator_is_not_emailed(self):
        recipients = daily_report_recipients()
        self.assertEqual(
            [recipient["email"] for recipient in recipients],
            ["warehouse-manager@example.com"],
        )

    def test_snapshot_includes_all_active_warehouses_without_addresses(self):
        self.central.address_line_1 = "Private address"
        self.central.save(update_fields=("address_line_1", "updated_at"))
        snapshot = build_daily_inventory_snapshot()
        self.assertEqual(snapshot["grand_totals"]["warehouse_count"], 2)
        self.assertEqual(snapshot["grand_totals"]["on_hand"], 6)
        self.assertEqual(snapshot["grand_totals"]["available"], 5)
        self.assertNotIn("address", snapshot["warehouses"][0])

    @override_settings(BOOKSTORE_DAILY_REPORT_ENABLED=True)
    @patch(
        "apps.bookstore_inventory.services.daily_reports.send_custom_email",
        return_value=True,
    )
    def test_daily_summary_sends_one_personalized_email_per_manager(self, mocked_send):
        result = send_daily_inventory_summary()
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["sent"], 1)
        self.assertEqual(mocked_send.call_count, 1)
        kwargs = mocked_send.call_args.kwargs
        self.assertEqual(kwargs["to"], "warehouse-manager@example.com")
        self.assertEqual(kwargs["context"]["grand_totals"]["available"], 5)
