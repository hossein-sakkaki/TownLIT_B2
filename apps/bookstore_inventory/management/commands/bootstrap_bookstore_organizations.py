# apps/bookstore_inventory/management/commands/bootstrap_bookstore_organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.bookstore_inventory.constants import (
    InboundSourceType, OrganizationRoleType, RecipientType,
)
from apps.bookstore_inventory.models import (
    Book, BookEdition, BookOrder, InboundShipment, OrganizationRecord,
    OrganizationRole,
)
from apps.bookstore_inventory.models.organizations import normalize_organization_name


class Command(BaseCommand):
    help = "Idempotently convert existing bookstore organization-name strings into directory records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report changes and roll the transaction back.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        counters = {"organizations": 0, "links": 0, "roles": 0}

        def resolve(name, role):
            value = (name or "").strip()
            if not value:
                return None
            normalized = normalize_organization_name(value)
            organization = OrganizationRecord.objects.filter(
                normalized_name=normalized,
                merged_into__isnull=True,
            ).order_by("id").first()
            if organization is None:
                organization = OrganizationRecord.objects.create(official_name=value)
                counters["organizations"] += 1
            _, created = OrganizationRole.objects.get_or_create(
                organization=organization, role=role,
                defaults={"is_active": True},
            )
            counters["roles"] += int(created)
            return organization

        for book in Book.objects.filter(publisher__isnull=True).exclude(publisher_name=""):
            book.publisher = resolve(book.publisher_name, OrganizationRoleType.PUBLISHER)
            book.save(update_fields=("publisher", "updated_at"))
            counters["links"] += 1

        for book in Book.objects.filter(rights_holder__isnull=True).exclude(copyright_holder=""):
            book.rights_holder = resolve(book.copyright_holder, OrganizationRoleType.RIGHTS_HOLDER)
            book.save(update_fields=("rights_holder", "updated_at"))
            counters["links"] += 1

        for edition in BookEdition.objects.filter(publisher__isnull=True).exclude(edition_publisher_name=""):
            edition.publisher = resolve(edition.edition_publisher_name, OrganizationRoleType.PUBLISHER)
            edition.save(update_fields=("publisher", "updated_at"))
            counters["links"] += 1

        for shipment in InboundShipment.objects.exclude(supplier_name=""):
            if shipment.source_type == InboundSourceType.DONATION and not shipment.donor_id:
                shipment.donor = resolve(shipment.supplier_name, OrganizationRoleType.DONOR)
                shipment.donor_name = shipment.donor_name or shipment.supplier_name
                shipment.save(update_fields=("donor", "donor_name", "updated_at"))
                counters["links"] += 1
            elif not shipment.supplier_id:
                role = (
                    OrganizationRoleType.CONSIGNMENT_PARTNER
                    if shipment.source_type == InboundSourceType.CONSIGNMENT
                    else OrganizationRoleType.SUPPLIER
                )
                shipment.supplier = resolve(shipment.supplier_name, role)
                shipment.save(update_fields=("supplier", "updated_at"))
                counters["links"] += 1

        for order in BookOrder.objects.filter(
            recipient_type=RecipientType.ORGANIZATION,
            recipient_organization__isnull=True,
        ).exclude(organization_name=""):
            order.recipient_organization = resolve(
                order.organization_name, OrganizationRoleType.CUSTOMER,
            )
            order.save(update_fields=("recipient_organization", "updated_at"))
            counters["links"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Organization bootstrap: "
                f"{counters['organizations']} created, "
                f"{counters['roles']} roles added, "
                f"{counters['links']} records linked."
            )
        )
        if options["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run complete; all changes rolled back."))
