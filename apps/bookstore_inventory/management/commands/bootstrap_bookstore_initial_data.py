# apps/bookstore_inventory/management/commands/bootstrap_bookstore_initial_data.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-17.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.bookstore_inventory.constants import (
    BookType,
    InboundPaymentStatus,
    InboundSourceType,
    InventoryCondition,
    LocationType,
    OrganizationRoleType,
    PricingMode,
    WarehouseStaffRole,
)
from apps.bookstore_inventory.models import (
    Book,
    BookEdition,
    InboundShipment,
    InboundShipmentItem,
    InventoryBalance,
    OrganizationRecord,
    OrganizationRole,
    Warehouse,
    WarehouseLocation,
    WarehouseStaffAssignment,
)
from apps.bookstore_inventory.services.inventory import (
    post_inbound_shipment_to_stock,
)
from apps.bookstore_inventory.services.numbering import (
    generate_shipment_number,
)


CustomUser = get_user_model()


DEFAULT_USER_ID = 1
DEFAULT_STOCK_WAREHOUSE_CODE = "YVR-HQ"

BOOKSTORE_CURRENCY = "CAD"

INITIAL_SHIPMENT_REFERENCE = "ELAM-INITIAL-2026"


WAREHOUSES = (
    {
        "name": "TownLIT Central Office Warehouse",
        "code": "YVR-HQ",
        "address_line_1": "2880 Woodsia Pl",
        "address_line_2": "",
        "city": "Coquitlam",
        "province_state": "British Columbia",
        "postal_code": "V3E 2Y2",
        "country": "Canada",
        "description": (
            "TownLIT central office bookstore inventory warehouse."
        ),
    },
    {
        "name": "CA Church Warehouse",
        "code": "YVR-CA-CHURCH",
        "address_line_1": "2601 Spuraway Ave",
        "address_line_2": "",
        "city": "Coquitlam",
        "province_state": "British Columbia",
        "postal_code": "V3C 2C4",
        "country": "Canada",
        "description": (
            "TownLIT bookstore inventory warehouse located at CA Church."
        ),
    },
    {
        "name": "North Vancouver Warehouse",
        "code": "NVAN-01",
        "address_line_1": "600 Mountain Hwy",
        "address_line_2": "",
        "city": "North Vancouver",
        "province_state": "British Columbia",
        "postal_code": "V7J 1H7",
        "country": "Canada",
        "description": (
            "TownLIT North Vancouver bookstore inventory warehouse."
        ),
    },
)


ELAM = {
    "official_name": "Elam Ministries",
    "display_name": "Elam Ministries",
    "registration_number": "1099143",
    "website": "https://www.elam.com",
    "email": "contact@elam.com",
    "phone": "+44 1483 427778",
    "address_line_1": "Grenville, Grenville Road",
    "address_line_2": "",
    "city": "Godalming",
    "province_state": "Surrey",
    "postal_code": "GU8 6AX",
    "country": "United Kingdom",
    "is_active": True,
    "notes": (
        "Registered charity in England and Wales, charity number 1099143. "
        "Public correspondence address: P.O. Box 75, Godalming, Surrey, "
        "GU8 6YP, United Kingdom. "
        "Public contact: contact@elam.com / +44 1483 427778."
    ),
}


CATALOGUE = (
    {
        "key": "persian_new_testament_nmv_burgundy",
        "book": {
            "title": "Persian New Testament — New Millennium Version",
            "book_type": BookType.NEW_TESTAMENT,
            "original_language": "fa",
            "subject_category": "Bible / New Testament",
            "description": (
                "Persian New Testament in the New Millennium Version."
            ),
            "is_active": True,
        },
        "edition": {
            "edition_code": "ELAM-NMV-NT-BURGUNDY-GILT",
            "edition_name": (
                "New Millennium Version — Burgundy Gilded Edition"
            ),
            "language": "fa",
            "translation_name": "New Millennium Version",
            "pricing_mode": PricingMode.FREE,
            "fixed_price": Decimal("0.00"),
            "minimum_donation": Decimal("0.00"),
            "currency": BOOKSTORE_CURRENCY,
            "is_sellable": False,
            "is_distributable": True,
            "is_active": True,
            "notes": (
                "Burgundy cover with gilded page edges and gold foil stamping. "
                "Initial inventory received from Elam Ministries."
            ),
        },
        "quantity": 100,
        "lot_number": "ELAM-INITIAL-NMV-NT-BURGUNDY-GILT",
    },
    {
        "key": "persian_bible_nmv_standard_burgundy",
        "book": {
            "title": (
                "Persian Bible — New Millennium Version — Standard Edition"
            ),
            "book_type": BookType.BIBLE,
            "original_language": "fa",
            "subject_category": "Bible",
            "description": (
                "Persian Bible in the New Millennium Version, standard edition."
            ),
            "is_active": True,
        },
        "edition": {
            "edition_code": "ELAM-NMV-BIBLE-STANDARD-BURGUNDY-GILT",
            "edition_name": (
                "New Millennium Version — Standard Burgundy Gilded Edition"
            ),
            "language": "fa",
            "translation_name": "New Millennium Version",
            "pricing_mode": PricingMode.FREE,
            "fixed_price": Decimal("0.00"),
            "minimum_donation": Decimal("0.00"),
            "currency": BOOKSTORE_CURRENCY,
            "is_sellable": False,
            "is_distributable": True,
            "is_active": True,
            "notes": (
                "Standard burgundy cover with gilded page edges and "
                "gold foil stamping. "
                "Initial inventory received from Elam Ministries."
            ),
        },
        "quantity": 6,
        "lot_number": "ELAM-INITIAL-NMV-BIBLE-STANDARD-BURGUNDY-GILT",
    },
    {
        "key": "persian_bible_nmv_black",
        "book": {
            "title": (
                "Persian Bible — New Millennium Version — Black Edition"
            ),
            "book_type": BookType.BIBLE,
            "original_language": "fa",
            "subject_category": "Bible",
            "description": (
                "Persian Bible in the New Millennium Version, black edition."
            ),
            "is_active": True,
        },
        "edition": {
            "edition_code": "ELAM-NMV-BIBLE-BLACK-GILT",
            "edition_name": (
                "New Millennium Version — Black Gilded Edition"
            ),
            "language": "fa",
            "translation_name": "New Millennium Version",
            "pricing_mode": PricingMode.FIXED_PRICE,
            "fixed_price": Decimal("40.00"),
            "minimum_donation": Decimal("0.00"),
            "currency": BOOKSTORE_CURRENCY,
            "is_sellable": True,
            "is_distributable": True,
            "is_active": True,
            "notes": (
                "Black cover with gilded page edges and gold foil stamping. "
                "TownLIT selling price: 40 CAD. "
                "Initial inventory received from Elam Ministries."
            ),
        },
        "quantity": 34,
        "lot_number": "ELAM-INITIAL-NMV-BIBLE-BLACK-GILT",
    },
)


class Command(BaseCommand):
    help = (
        "Create the initial TownLIT bookstore warehouses, staff assignments, "
        "Elam Ministries organization, initial Persian catalogue, and "
        "initial inbound shipment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            default=DEFAULT_USER_ID,
            help=(
                "Existing CustomUser responsible for the initial warehouses. "
                f"Default: {DEFAULT_USER_ID}."
            ),
        )

        parser.add_argument(
            "--stock-warehouse-code",
            default=DEFAULT_STOCK_WAREHOUSE_CODE,
            help=(
                "Warehouse receiving the initial Elam shipment. "
                f"Default: {DEFAULT_STOCK_WAREHOUSE_CODE}."
            ),
        )

        parser.add_argument(
            "--received-date",
            default="",
            help=(
                "Actual shipment receipt date in YYYY-MM-DD format. "
                "Default: today."
            ),
        )

        parser.add_argument(
            "--post-stock",
            action="store_true",
            help=(
                "Post the initial Elam shipment to permanent stock movements. "
                "Without this flag the shipment remains unposted."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Execute validation and database operations inside a transaction "
                "and roll everything back before completion."
            ),
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]

        stock_warehouse_code = str(
            options["stock_warehouse_code"]
        ).strip().upper()

        post_stock = bool(options["post_stock"])
        dry_run = bool(options["dry_run"])

        received_at = self._resolve_received_at(
            options["received_date"]
        )

        with transaction.atomic():
            user = self._get_responsible_user(
                user_id
            )

            warehouses = (
                self._create_warehouses_and_staff(
                    user=user
                )
            )

            stock_warehouse = warehouses.get(
                stock_warehouse_code
            )

            if stock_warehouse is None:
                raise CommandError(
                    "Unknown initial stock warehouse code: "
                    f"{stock_warehouse_code}"
                )

            main_location = (
                WarehouseLocation.objects.get(
                    warehouse=stock_warehouse,
                    code="MAIN",
                )
            )

            elam = self._create_elam_organization()

            editions = self._create_catalogue()

            shipment = self._create_initial_shipment(
                user=user,
                warehouse=stock_warehouse,
                location=main_location,
                donor=elam,
                editions=editions,
                received_at=received_at,
            )

            if post_stock:
                self._post_initial_stock(
                    shipment=shipment,
                    user=user,
                )

            self._print_summary(
                warehouses=warehouses,
                user=user,
                organization=elam,
                editions=editions,
                shipment=shipment,
            )

            if dry_run:
                transaction.set_rollback(True)

                self.stdout.write("")
                self.stdout.write(
                    self.style.WARNING(
                        "DRY RUN complete. "
                        "All database changes were rolled back."
                    )
                )
            else:
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS(
                        "TownLIT bookstore initial data bootstrap completed."
                    )
                )

    def _resolve_received_at(self, raw_value):
        raw_value = str(
            raw_value or ""
        ).strip()

        if not raw_value:
            return timezone.now()

        try:
            parsed_date = datetime.strptime(
                raw_value,
                "%Y-%m-%d",
            ).date()
        except ValueError as exc:
            raise CommandError(
                "--received-date must use YYYY-MM-DD."
            ) from exc

        naive_datetime = datetime.combine(
            parsed_date,
            time(hour=12),
        )

        return timezone.make_aware(
            naive_datetime,
            timezone.get_current_timezone(),
        )

    def _get_responsible_user(self, user_id):
        try:
            user = CustomUser.objects.get(
                pk=user_id
            )
        except CustomUser.DoesNotExist as exc:
            raise CommandError(
                f"CustomUser id={user_id} does not exist."
            ) from exc

        invalid_reasons = []

        if not getattr(
            user,
            "is_active",
            False,
        ):
            invalid_reasons.append("inactive")

        if getattr(
            user,
            "is_deleted",
            False,
        ):
            invalid_reasons.append("deleted")

        if getattr(
            user,
            "is_suspended",
            False,
        ):
            invalid_reasons.append("suspended")

        if getattr(
            user,
            "is_account_paused",
            False,
        ):
            invalid_reasons.append(
                "account paused"
            )

        if not (
            getattr(user, "is_admin", False)
            or getattr(
                user,
                "is_superuser",
                False,
            )
        ):
            invalid_reasons.append(
                "not an administrator or superuser"
            )

        if invalid_reasons:
            raise CommandError(
                f"CustomUser id={user_id} is not eligible for warehouse "
                f"responsibility: {', '.join(invalid_reasons)}."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Responsible user: {user} (id={user.pk})"
            )
        )

        return user

    def _create_warehouses_and_staff(
        self,
        *,
        user,
    ):
        warehouses = {}

        for spec in WAREHOUSES:
            warehouse, created = (
                Warehouse.objects.get_or_create(
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "address_line_1": spec[
                            "address_line_1"
                        ],
                        "address_line_2": spec[
                            "address_line_2"
                        ],
                        "city": spec["city"],
                        "province_state": spec[
                            "province_state"
                        ],
                        "postal_code": spec[
                            "postal_code"
                        ],
                        "country": spec["country"],
                        "description": spec[
                            "description"
                        ],
                        "is_active": True,
                    },
                )
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Created warehouse: "
                        f"{warehouse.name} ({warehouse.code})"
                    )
                )
            else:
                self.stdout.write(
                    "Warehouse already exists: "
                    f"{warehouse.name} ({warehouse.code})"
                )

            assignment, assignment_created = (
                WarehouseStaffAssignment.objects.get_or_create(
                    warehouse=warehouse,
                    user=user,
                    defaults={
                        "role": (
                            WarehouseStaffRole.PRIMARY_MANAGER
                        ),
                        "is_active": True,
                        "starts_at": timezone.now(),
                        "can_receive_stock": True,
                        "can_fulfill_orders": True,
                        "can_transfer_stock": True,
                        "can_count_stock": True,
                        "can_adjust_stock": True,
                        "can_process_returns": True,
                        "notes": (
                            "Initial TownLIT bookstore warehouse "
                            "responsibility assignment."
                        ),
                    },
                )
            )

            if assignment_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Assigned {user} as Primary Manager."
                    )
                )
            else:
                self.stdout.write(
                    "  Staff assignment already exists: "
                    f"{assignment.get_role_display()}."
                )

            self._create_default_locations(
                warehouse
            )

            warehouses[
                warehouse.code
            ] = warehouse

        return warehouses

    def _create_default_locations(
        self,
        warehouse,
    ):
        locations = (
            {
                "code": "MAIN",
                "name": "Main Stock",
                "location_type": (
                    LocationType.ZONE
                ),
                "is_pickable": True,
                "is_active": True,
                "notes": (
                    "Primary bookstore inventory location."
                ),
            },
            {
                "code": "RECEIVING",
                "name": "Receiving",
                "location_type": (
                    LocationType.STAGING
                ),
                "is_pickable": False,
                "is_active": True,
                "notes": (
                    "Temporary receiving and verification area."
                ),
            },
        )

        for spec in locations:
            location, created = (
                WarehouseLocation.objects.get_or_create(
                    warehouse=warehouse,
                    code=spec["code"],
                    defaults={
                        "name": spec["name"],
                        "location_type": spec[
                            "location_type"
                        ],
                        "is_pickable": spec[
                            "is_pickable"
                        ],
                        "is_active": spec[
                            "is_active"
                        ],
                        "notes": spec["notes"],
                    },
                )
            )

            if created:
                self.stdout.write(
                    "  Created location: "
                    f"{location.code} — {location.name}"
                )

    def _create_elam_organization(self):
        organization, created = (
            OrganizationRecord.objects.get_or_create(
                official_name=ELAM[
                    "official_name"
                ],
                defaults={
                    "display_name": ELAM[
                        "display_name"
                    ],
                    "registration_number": ELAM[
                        "registration_number"
                    ],
                    "website": ELAM["website"],
                    "email": ELAM["email"],
                    "phone": ELAM["phone"],
                    "address_line_1": ELAM[
                        "address_line_1"
                    ],
                    "address_line_2": ELAM[
                        "address_line_2"
                    ],
                    "city": ELAM["city"],
                    "province_state": ELAM[
                        "province_state"
                    ],
                    "postal_code": ELAM[
                        "postal_code"
                    ],
                    "country": ELAM["country"],
                    "is_active": ELAM[
                        "is_active"
                    ],
                    "notes": ELAM["notes"],
                },
            )
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    "Created organization: Elam Ministries"
                )
            )
        else:
            self.stdout.write(
                "Organization already exists: Elam Ministries"
            )

        for role in (
            OrganizationRoleType.DONOR,
            OrganizationRoleType.SUPPLIER,
        ):
            OrganizationRole.objects.get_or_create(
                organization=organization,
                role=role,
                defaults={
                    "is_active": True,
                    "notes": (
                        "Initial TownLIT bookstore relationship."
                    ),
                },
            )

        return organization

    def _create_catalogue(self):
        editions = {}

        for spec in CATALOGUE:
            book_defaults = dict(
                spec["book"]
            )

            title = book_defaults.pop(
                "title"
            )

            book, book_created = (
                Book.objects.get_or_create(
                    title=title,
                    defaults=book_defaults,
                )
            )

            if book_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created book: {book.title}"
                    )
                )
            else:
                self.stdout.write(
                    f"Book already exists: {book.title}"
                )

            edition_defaults = dict(
                spec["edition"]
            )

            edition_code = (
                edition_defaults.pop(
                    "edition_code"
                )
            )

            edition, edition_created = (
                BookEdition.objects.get_or_create(
                    edition_code=edition_code,
                    defaults={
                        "book": book,
                        **edition_defaults,
                    },
                )
            )

            if (
                not edition_created
                and edition.book_id != book.pk
            ):
                raise CommandError(
                    f"Edition code {edition_code} already exists "
                    "for a different book."
                )

            if edition_created:
                self.stdout.write(
                    self.style.SUCCESS(
                        "  Created edition: "
                        f"{edition.edition_code}"
                    )
                )
            else:
                self.stdout.write(
                    "  Edition already exists: "
                    f"{edition.edition_code}"
                )

            editions[
                spec["key"]
            ] = edition

        return editions

    def _create_initial_shipment(
        self,
        *,
        user,
        warehouse,
        location,
        donor,
        editions,
        received_at,
    ):
        existing_shipments = (
            InboundShipment.objects.filter(
                invoice_reference=(
                    INITIAL_SHIPMENT_REFERENCE
                )
            )
            .select_related(
                "warehouse"
            )
        )

        shipment_count = (
            existing_shipments.count()
        )

        if shipment_count > 1:
            raise CommandError(
                "More than one shipment uses reference "
                f"{INITIAL_SHIPMENT_REFERENCE}. "
                "Resolve the duplicate before continuing."
            )

        if shipment_count == 1:
            shipment = (
                existing_shipments.first()
            )

            if (
                shipment.warehouse_id
                != warehouse.pk
            ):
                raise CommandError(
                    "The initial Elam shipment already exists in "
                    f"{shipment.warehouse.code}. "
                    "A second initial shipment will not be created."
                )

            self.stdout.write(
                "Initial shipment already exists: "
                f"{shipment.shipment_number}"
            )

        else:
            shipment = InboundShipment(
                shipment_number=(
                    generate_shipment_number()
                ),
                warehouse=warehouse,
                source_type=(
                    InboundSourceType.DONATION
                ),
                donor=donor,
                donor_name=str(donor),
                invoice_reference=(
                    INITIAL_SHIPMENT_REFERENCE
                ),
                received_at=received_at,
                shipping_cost=Decimal(
                    "0.00"
                ),
                other_cost=Decimal(
                    "0.00"
                ),
                currency=BOOKSTORE_CURRENCY,
                payment_status=(
                    InboundPaymentStatus.NOT_REQUIRED
                ),
                created_by=user,
                notes=(
                    "Initial TownLIT bookstore inventory received "
                    "from Elam Ministries."
                ),
            )

            shipment.full_clean()
            shipment.save()

            self.stdout.write(
                self.style.SUCCESS(
                    "Created initial inbound shipment: "
                    f"{shipment.shipment_number}"
                )
            )

        if shipment.is_stock_posted:
            self.stdout.write(
                self.style.WARNING(
                    "The initial shipment has already been posted. "
                    "Shipment lines will not be modified."
                )
            )
            return shipment

        for spec in CATALOGUE:
            edition = editions[
                spec["key"]
            ]

            item, created = (
                InboundShipmentItem.objects.get_or_create(
                    shipment=shipment,
                    book_edition=edition,
                    defaults={
                        "location": location,
                        "lot_number": spec[
                            "lot_number"
                        ],
                        "condition": (
                            InventoryCondition.NEW
                        ),
                        "quantity": spec[
                            "quantity"
                        ],
                        "unit_cost": Decimal(
                            "0.00"
                        ),
                        "notes": (
                            "Initial inventory received "
                            "from Elam Ministries."
                        ),
                    },
                )
            )

            if created:
                item.full_clean()
                item.save()

                self.stdout.write(
                    self.style.SUCCESS(
                        "  Added shipment line: "
                        f"{edition.edition_code} "
                        f"× {item.quantity}"
                    )
                )
                continue

            differences = []

            if item.quantity != spec["quantity"]:
                differences.append(
                    f"quantity={item.quantity}; "
                    f"expected={spec['quantity']}"
                )

            if item.location_id != location.pk:
                differences.append(
                    "location differs"
                )

            if (
                item.lot_number
                != spec["lot_number"]
            ):
                differences.append(
                    "lot number differs"
                )

            if (
                item.unit_cost
                != Decimal("0.00")
            ):
                differences.append(
                    f"unit cost={item.unit_cost}; "
                    "expected=0.00"
                )

            if differences:
                raise CommandError(
                    "Existing initial shipment line "
                    f"{edition.edition_code} differs from "
                    "the bootstrap definition: "
                    f"{', '.join(differences)}. "
                    "Operational data will not be overwritten automatically."
                )

            self.stdout.write(
                "  Shipment line already exists: "
                f"{edition.edition_code} × {item.quantity}"
            )

        shipment.recalculate_totals(
            save=True
        )
        shipment.refresh_from_db()

        return shipment

    def _post_initial_stock(
        self,
        *,
        shipment,
        user,
    ):
        if shipment.is_stock_posted:
            self.stdout.write(
                self.style.WARNING(
                    f"Shipment {shipment.shipment_number} "
                    "is already posted. "
                    "No additional stock movements were created."
                )
            )
            return

        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "Posting the initial shipment "
                "to permanent inventory..."
            )
        )

        movements = (
            post_inbound_shipment_to_stock(
                shipment_id=shipment.pk,
                user=user,
            )
        )

        shipment.refresh_from_db()

        self.stdout.write(
            self.style.SUCCESS(
                f"Posted {len(movements)} permanent "
                "stock movement(s)."
            )
        )

    def _print_summary(
        self,
        *,
        warehouses,
        user,
        organization,
        editions,
        shipment,
    ):
        self.stdout.write("")
        self.stdout.write(
            "========================================"
        )
        self.stdout.write(
            "TownLIT Bookstore Initial Data Bootstrap"
        )
        self.stdout.write(
            "========================================"
        )

        self.stdout.write(
            f"Responsible user: "
            f"{user} (id={user.pk})"
        )

        self.stdout.write("")
        self.stdout.write(
            "Warehouses:"
        )

        for warehouse in warehouses.values():
            self.stdout.write(
                f"  - {warehouse.name} "
                f"[{warehouse.code}]"
            )

        self.stdout.write("")
        self.stdout.write(
            f"Organization: {organization}"
        )

        self.stdout.write("")
        self.stdout.write(
            "Initial catalogue:"
        )

        for spec in CATALOGUE:
            edition = editions[
                spec["key"]
            ]

            self.stdout.write(
                f"  - {edition.book.title} | "
                f"{edition.edition_code} | "
                f"quantity={spec['quantity']} | "
                f"{edition.default_display_price}"
            )

        self.stdout.write("")
        self.stdout.write(
            "Initial shipment: "
            f"{shipment.shipment_number}"
        )
        self.stdout.write(
            "Reference: "
            f"{shipment.invoice_reference}"
        )
        self.stdout.write(
            "Warehouse: "
            f"{shipment.warehouse.code}"
        )
        self.stdout.write(
            "Stock posted: "
            f"{'YES' if shipment.is_stock_posted else 'NO'}"
        )

        if not shipment.is_stock_posted:
            return

        self.stdout.write("")
        self.stdout.write(
            "Inventory balances:"
        )

        balances = (
            InventoryBalance.objects.filter(
                warehouse=shipment.warehouse,
                book_edition__in=(
                    editions.values()
                ),
            )
            .select_related(
                "book_edition__book"
            )
            .order_by(
                "book_edition__edition_code"
            )
        )

        for balance in balances:
            self.stdout.write(
                "  - "
                f"{balance.book_edition.edition_code}: "
                f"on_hand={balance.on_hand_quantity}, "
                f"reserved={balance.reserved_quantity}, "
                f"unavailable={balance.unavailable_quantity}, "
                f"available={balance.available_quantity}"
            )

# docker compose exec -T backend python manage.py bootstrap_bookstore_initial_data

# docker compose exec -T backend \
#   python manage.py bootstrap_bookstore_initial_data --post-stock