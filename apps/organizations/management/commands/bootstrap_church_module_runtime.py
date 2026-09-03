# apps/organizations/management/commands/bootstrap_church_module_runtime.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from django.core.management.base import BaseCommand

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.models import OrganizationModuleActivation
from apps.organizations.modules.church.services.bootstrap import bootstrap_church_workspace


class Command(BaseCommand):
    help = "Initialize Church workspaces and Church-specific roles for existing activations."

    def handle(self, *args, **options):
        activations = (
            OrganizationModuleActivation.objects
            .filter(module__key=OrganizationModuleKey.CHURCH)
            .select_related("organization", "module")
            .order_by("id")
        )

        count = 0

        for activation in activations.iterator():
            bootstrap_church_workspace(
                activation=activation,
                actor=None,
            )
            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Initialized Church runtime for {count} activation(s)."
            )
        )
