# apps/bookstore_inventory/tests/test_workflows.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from decimal import Decimal
from io import StringIO
from datetime import timedelta

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    AdjustmentReason, DocumentStatus, InboundPaymentStatus, InboundSourceType,
    OrderType, PricingMode, ReservationStatus, StockCountStatus, TransferStatus,
    WarehouseStaffRole,
)
from apps.bookstore_inventory.models import (
    Book, BookEdition, BookOrder, BookOrderItem, InboundShipment,
    InboundPayment, InboundPaymentSchedule, InboundShipmentItem,
    InventoryBalance, OrganizationAlias,
    OrganizationRecord, StockAdjustment, StockAdjustmentItem, StockCount,
    StockCountItem, StockTransfer, StockTransferItem, Warehouse,
    WarehouseStaffAssignment, CashLedgerEntry,
)
from apps.bookstore_inventory.services.inventory import (
    fulfill_book_order, post_inbound_shipment_to_stock,
)
from apps.bookstore_inventory.services.reservations import reserve_book_order
from apps.bookstore_inventory.services.operations import (
    dispatch_stock_transfer, post_stock_adjustment, post_stock_count,
    receive_stock_transfer, snapshot_stock_count,
)


class OrganizationDirectoryTests(TestCase):
    def test_normalizes_names_without_changing_display_value(self):
        organization = OrganizationRecord.objects.create(
            official_name="  Ilam   Publishing  ", country="Canada"
        )
        self.assertEqual(organization.official_name, "Ilam   Publishing")
        self.assertEqual(organization.normalized_name, "ilam publishing")
        OrganizationAlias.objects.create(organization=organization, name="ILAM Pub.")
        self.assertEqual(organization.aliases.get().normalized_name, "ilam pub")

    def test_bootstrap_command_is_idempotent(self):
        book = Book.objects.create(
            title="Directory Test", publisher_name="Ilam Publishing"
        )
        call_command("bootstrap_bookstore_organizations", stdout=StringIO())
        book.refresh_from_db()
        self.assertEqual(book.publisher.official_name, "Ilam Publishing")
        call_command("bootstrap_bookstore_organizations", stdout=StringIO())
        self.assertEqual(OrganizationRecord.objects.count(), 1)

    def test_controlled_merge_repoints_relations_and_preserves_source(self):
        source = OrganizationRecord.objects.create(official_name="Ilam Pub")
        target = OrganizationRecord.objects.create(official_name="Ilam Publishing")
        book = Book.objects.create(title="Merge Test", publisher=source)
        call_command(
            "merge_bookstore_organizations", source.pk, target.pk,
            stdout=StringIO(),
        )
        book.refresh_from_db()
        source.refresh_from_db()
        self.assertEqual(book.publisher, target)
        self.assertEqual(source.merged_into, target)
        self.assertFalse(source.is_active)


class InventoryWorkflowTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(name="Main Warehouse", code="MAIN")
        self.book = Book.objects.create(title="Test Bible", original_language="Persian")
        self.edition = BookEdition.objects.create(
            book=self.book, edition_code="TEST-NMV", language="Persian",
            pricing_mode=PricingMode.FIXED_PRICE,
            fixed_price=Decimal("40.00"), currency="CAD",
        )

    def _receive_stock(self, quantity=5):
        shipment = InboundShipment.objects.create(
            shipment_number="INB-TEST", warehouse=self.warehouse,
            source_type=InboundSourceType.DONATION,
            payment_status=InboundPaymentStatus.NOT_REQUIRED,
            received_at=timezone.now(), currency="CAD",
        )
        InboundShipmentItem.objects.create(
            shipment=shipment, book_edition=self.edition,
            quantity=quantity, unit_cost=Decimal("0.00"),
        )
        post_inbound_shipment_to_stock(shipment.pk)
        return shipment

    def test_inbound_reservation_and_fulfilment_are_consistent(self):
        self._receive_stock(quantity=5)
        order = BookOrder.objects.create(
            order_number="ORD-TEST", order_type=OrderType.SALE,
            recipient_first_name="Test", currency="CAD",
        )
        item = BookOrderItem.objects.create(
            order=order, book_edition=self.edition,
            warehouse=self.warehouse, quantity=2,
            unit_price=Decimal("40.00"),
        )

        reserve_book_order(order.pk)
        balance = InventoryBalance.objects.get(
            warehouse=self.warehouse, book_edition=self.edition,
        )
        self.assertEqual(balance.on_hand_quantity, 5)
        self.assertEqual(balance.reserved_quantity, 2)
        self.assertEqual(balance.available_quantity, 3)

        fulfill_book_order(order.pk)
        balance.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(balance.on_hand_quantity, 3)
        self.assertEqual(balance.reserved_quantity, 0)
        self.assertTrue(order.is_fulfilled)
        self.assertEqual(
            item.reservations.get().status,
            ReservationStatus.CONSUMED,
        )

    def test_transfer_stock_count_and_adjustment_create_auditable_movements(self):
        self._receive_stock(quantity=10)
        destination = Warehouse.objects.create(name="Second Warehouse", code="SECOND")
        lot = self.edition.inventory_lots.get(warehouse=self.warehouse)
        transfer = StockTransfer.objects.create(
            transfer_number="TRF-TEST", from_warehouse=self.warehouse,
            to_warehouse=destination,
        )
        StockTransferItem.objects.create(
            transfer=transfer, book_edition=self.edition,
            source_lot=lot, quantity=3,
        )
        dispatch_stock_transfer(transfer.pk)
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, TransferStatus.DISPATCHED)
        receive_stock_transfer(transfer.pk)
        self.assertEqual(
            InventoryBalance.objects.get(
                warehouse=destination, book_edition=self.edition,
            ).on_hand_quantity,
            3,
        )

        stock_count = StockCount.objects.create(
            count_number="CNT-TEST", warehouse=destination,
        )
        count_item = StockCountItem.objects.create(
            stock_count=stock_count, book_edition=self.edition,
            counted_quantity=2,
        )
        snapshot_stock_count(stock_count.pk)
        count_item.refresh_from_db()
        self.assertEqual(count_item.expected_quantity, 3)
        post_stock_count(stock_count.pk)
        stock_count.refresh_from_db()
        self.assertEqual(stock_count.status, StockCountStatus.POSTED)

        adjustment = StockAdjustment.objects.create(
            adjustment_number="ADJ-TEST", warehouse=destination,
            status=DocumentStatus.DRAFT, reason=AdjustmentReason.FOUND,
        )
        StockAdjustmentItem.objects.create(
            adjustment=adjustment, book_edition=self.edition,
            quantity_delta=1,
        )
        post_stock_adjustment(adjustment.pk)
        self.assertEqual(
            InventoryBalance.objects.get(
                warehouse=destination, book_edition=self.edition,
            ).on_hand_quantity,
            3,
        )


class OperationalReadinessTests(TestCase):
    def setUp(self):
        self.warehouse = Warehouse.objects.create(
            name="TownLIT Central Office Warehouse",
            code="YVR-HQ",
        )
        self.user = get_user_model().objects.create_user(
            email="operator@example.com",
            username="operator",
            password="test-password",
        )
        if not self.user.is_active:
            self.user.is_active = True
            self.user.save(update_fields=("is_active",))
        self.user.user_permissions.add(
            Permission.objects.get(codename="post_inboundshipment")
        )
        self.book = Book.objects.create(title="Operational Test Bible")
        self.edition = BookEdition.objects.create(
            book=self.book,
            edition_code="OPS-TEST",
            language="Persian",
            pricing_mode=PricingMode.FIXED_PRICE,
            fixed_price=Decimal("40.00"),
            currency="CAD",
        )

    def _purchase_shipment(self):
        shipment = InboundShipment.objects.create(
            warehouse=self.warehouse,
            source_type=InboundSourceType.PURCHASE,
            received_at=timezone.now(),
            currency="CAD",
        )
        InboundShipmentItem.objects.create(
            shipment=shipment,
            book_edition=self.edition,
            quantity=10,
            unit_cost=Decimal("10.00"),
        )
        shipment.refresh_from_db()
        return shipment

    def test_document_numbers_are_generated_in_the_model_layer(self):
        shipment = self._purchase_shipment()
        order = BookOrder.objects.create(
            recipient_first_name="Test",
            currency="CAD",
        )
        transfer = StockTransfer.objects.create(
            from_warehouse=self.warehouse,
            to_warehouse=Warehouse.objects.create(name="Second", code="SECOND"),
        )
        self.assertTrue(shipment.shipment_number.startswith("INB-"))
        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertTrue(transfer.transfer_number.startswith("TRF-"))

    def test_donation_status_is_normalized_and_supplier_payments_are_rejected(self):
        shipment = InboundShipment(
            warehouse=self.warehouse,
            source_type=InboundSourceType.DONATION,
            received_at=timezone.now(),
            currency="CAD",
            shipping_cost=Decimal("25.00"),
        )
        shipment.full_clean()
        shipment.save()
        shipment.recalculate_totals()
        self.assertEqual(
            shipment.payment_status,
            InboundPaymentStatus.NOT_REQUIRED,
        )
        self.assertEqual(shipment.total_cost, Decimal("25.00"))
        self.assertEqual(shipment.amount_due, Decimal("0.00"))
        payment = InboundPayment(
            shipment=shipment,
            amount=Decimal("10.00"),
            currency="CAD",
            paid_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            payment.full_clean()

    def test_payment_schedule_tracks_partial_paid_and_overdue(self):
        shipment = self._purchase_shipment()
        schedule = InboundPaymentSchedule.objects.create(
            shipment=shipment,
            due_date=timezone.localdate() - timedelta(days=1),
            amount=Decimal("100.00"),
            currency="CAD",
        )
        payment = InboundPayment(
            shipment=shipment,
            schedule=schedule,
            amount=Decimal("30.00"),
            currency="CAD",
            paid_at=timezone.now(),
        )
        payment.full_clean()
        payment.save()
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, "partial")
        self.assertEqual(schedule.remaining_amount, Decimal("70.00"))
        self.assertTrue(schedule.is_overdue)

        second_payment = InboundPayment(
            shipment=shipment,
            schedule=schedule,
            amount=Decimal("70.00"),
            currency="CAD",
            paid_at=timezone.now(),
        )
        second_payment.full_clean()
        second_payment.save()
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, "paid")
        self.assertFalse(schedule.is_overdue)

    def test_irreversible_stock_post_requires_warehouse_capability(self):
        shipment = self._purchase_shipment()
        with self.assertRaises(ValidationError):
            post_inbound_shipment_to_stock(shipment.pk, user=self.user)

        assignment = WarehouseStaffAssignment.objects.create(
            warehouse=self.warehouse,
            user=self.user,
            role=WarehouseStaffRole.OPERATOR,
        )
        with self.assertRaises(ValidationError):
            post_inbound_shipment_to_stock(shipment.pk, user=self.user)

        assignment.can_receive_stock = True
        assignment.save(update_fields=("can_receive_stock", "updated_at"))
        movements = post_inbound_shipment_to_stock(shipment.pk, user=self.user)
        self.assertEqual(len(movements), 1)

    def test_cross_currency_payment_reduces_invoice_and_ledgers_actual_cash(self):
        shipment = InboundShipment.objects.create(
            warehouse=self.warehouse,
            source_type=InboundSourceType.PURCHASE,
            received_at=timezone.now(),
            currency="GBP",
        )
        InboundShipmentItem.objects.create(
            shipment=shipment,
            book_edition=self.edition,
            quantity=10,
            unit_cost=Decimal("10.00"),
        )
        payment = InboundPayment(
            shipment=shipment,
            amount=Decimal("100.00"),
            currency="GBP",
            settlement_amount=Decimal("170.00"),
            settlement_currency="CAD",
            exchange_rate=Decimal("0.58823529"),
            paid_at=timezone.now(),
        )
        payment.full_clean()
        payment.save()
        shipment.refresh_from_db()
        ledger = CashLedgerEntry.objects.get(
            ledger_key=f"inbound_payment:{payment.pk}"
        )
        self.assertEqual(shipment.amount_paid, Decimal("100.00"))
        self.assertEqual(shipment.amount_due, Decimal("0.00"))
        self.assertEqual(ledger.amount, Decimal("170.00"))
        self.assertEqual(ledger.currency, "CAD")


class UnifiedAdminTests(TestCase):
    def _superuser(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email="admin-workspace@example.com",
            username="admin-workspace",
            password="test-password",
        )
        user.is_superuser = True
        concrete_fields = {field.name for field in user_model._meta.fields}
        if "is_admin" in concrete_fields:
            user.is_admin = True
        if "is_staff" in concrete_fields:
            user.is_staff = True
        user.save()
        return user

    def test_warehouse_contact_is_sourced_from_user_assignment(self):
        warehouse_fields = {field.name for field in Warehouse._meta.fields}
        self.assertNotIn("contact_name", warehouse_fields)
        self.assertNotIn("contact_phone", warehouse_fields)

        assignment = WarehouseStaffAssignment.objects.create(
            warehouse=Warehouse.objects.create(name="Unified", code="UNIFIED"),
            user=self._superuser(),
            role=WarehouseStaffRole.PRIMARY_MANAGER,
        )
        self.assertEqual(
            assignment.user_id,
            assignment.warehouse.staff.get().pk,
        )

    def test_admin_app_menu_has_one_bookstore_workspace_entry(self):
        request = RequestFactory().get("/admin/")
        request.user = self._superuser()
        bookstore_app = next(
            app
            for app in admin.site.get_app_list(request)
            if app["app_label"] == "bookstore_inventory"
        )
        self.assertEqual(
            [model["object_name"] for model in bookstore_app["models"]],
            ["BookstoreWorkspace"],
        )
