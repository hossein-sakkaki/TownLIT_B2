# apps/organizations/management/commands/bootstrap_organization_modules.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.management.base import BaseCommand

from apps.organizations.services.module_catalog import (
    bootstrap_organization_module_catalog,
)


class Command(BaseCommand):
    help = "Bootstrap the TownLIT organization module and entitlement catalog."

    def handle(self, *args, **options):
        modules = bootstrap_organization_module_catalog()

        self.stdout.write(
            self.style.SUCCESS(
                f"Bootstrapped {len(modules)} organization modules."
            )
        )

        for module in modules.values():
            self.stdout.write(
                f"- {module.key}: {module.entitlement_key}"
            )
