# -*- coding: utf-8 -*-
# Seed/update SpiritualService records based on sensitive/standard choices.

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.profiles.models import SpiritualService
from apps.profiles.constants import SENSITIVE_MINISTRY_CHOICES, STANDARD_MINISTRY_CHOICES

class Command(BaseCommand):
    help = "Seed/update SpiritualService catalog from SENSITIVE/STANDARD choices. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Deactivate services not present in current catalog.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        prune = options.get("prune", False)
        dry_run = options.get("dry_run", False)

        # Build dictionaries: {code: label}
        sensitive_map = dict(SENSITIVE_MINISTRY_CHOICES)
        standard_map = dict(STANDARD_MINISTRY_CHOICES)

        # Desired full catalog
        catalog_map = {**sensitive_map, **standard_map}
        desired_codes = set(catalog_map.keys())
        sensitive_codes = set(sensitive_map.keys())

        created = 0
        updated = 0

        # Upsert each service from the catalog
        for code, label in catalog_map.items():
            defaults = {
                "description": label,               # optional: keep single-word label as description
                "is_sensitive": code in sensitive_codes,
                "is_active": True,
            }
            if dry_run:
                exists = SpiritualService.objects.filter(name=code).exists()
                if exists:
                    updated += 1
                else:
                    created += 1
                continue

            obj, was_created = SpiritualService.objects.update_or_create(
                name=code,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        deactivated = 0
        if prune:
            # Deactivate anything not in our catalog
            qs = SpiritualService.objects.exclude(name__in=desired_codes)
            if dry_run:
                deactivated = qs.count()
            else:
                deactivated = qs.update(is_active=False)

        # Report
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY RUN] would create={created}, update={updated}, "
                f"{'deactivate='+str(deactivated) if prune else 'deactivate=0 (no prune)'}"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Seeding completed. created={created}, updated={updated}, "
                f"{'deactivated='+str(deactivated) if prune else 'deactivated=0 (no prune)'}"
            ))


# docker compose exec backend python manage.py import_spiritual_services
