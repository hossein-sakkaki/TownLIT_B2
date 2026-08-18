# apps/bookstore_inventory/management/commands/merge_bookstore_organizations.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-04-01.
# Last Update by Hossein Sakkaki on 2026-08-17.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.bookstore_inventory.models import (
    Book, BookEdition, BookOrder, InboundShipment, OrganizationAlias,
    OrganizationProfileLink, OrganizationRecord, OrganizationRole, StockReturn,
)
from apps.bookstore_inventory.models.organizations import normalize_organization_name


class Command(BaseCommand):
    help = "Merge one duplicate internal organization record into a canonical target."

    def add_arguments(self, parser):
        parser.add_argument("source_id", type=int)
        parser.add_argument("target_id", type=int)
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        source_id, target_id = options["source_id"], options["target_id"]
        if source_id == target_id:
            raise CommandError("Source and target must differ.")
        try:
            source = OrganizationRecord.objects.select_for_update().get(pk=source_id)
            target = OrganizationRecord.objects.select_for_update().get(pk=target_id)
        except OrganizationRecord.DoesNotExist as exc:
            raise CommandError(str(exc)) from exc
        if target.merged_into_id:
            raise CommandError("Target is already merged into another organization.")

        updates = {
            "book publishers": Book.objects.filter(publisher=source).update(publisher=target),
            "book rights holders": Book.objects.filter(rights_holder=source).update(rights_holder=target),
            "edition publishers": BookEdition.objects.filter(publisher=source).update(publisher=target),
            "edition printers": BookEdition.objects.filter(printer=source).update(printer=target),
            "shipment suppliers": InboundShipment.objects.filter(supplier=source).update(supplier=target),
            "shipment donors": InboundShipment.objects.filter(donor=source).update(donor=target),
            "order recipients": BookOrder.objects.filter(recipient_organization=source).update(recipient_organization=target),
            "return suppliers": StockReturn.objects.filter(supplier=source).update(supplier=target),
            "profile links": OrganizationProfileLink.objects.filter(organization=source).update(organization=target),
        }
        for role in list(source.roles.all()):
            OrganizationRole.objects.update_or_create(
                organization=target, role=role.role,
                defaults={"is_active": role.is_active, "notes": role.notes},
            )
        source.roles.all().delete()

        alias_names = [source.official_name, source.display_name]
        alias_names.extend(source.aliases.values_list("name", flat=True))
        for name in filter(None, alias_names):
            OrganizationAlias.objects.get_or_create(
                organization=target,
                normalized_name=normalize_organization_name(name),
                defaults={"name": name},
            )
        source.aliases.all().delete()

        source.is_active = False
        source.merged_into = target
        source.save(update_fields=("is_active", "merged_into", "updated_at"))
        self.stdout.write(self.style.SUCCESS(
            f"Merged '{source}' into '{target}'. Updated: {updates}"
        ))
        if options["dry_run"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Dry run complete; all changes rolled back."))
