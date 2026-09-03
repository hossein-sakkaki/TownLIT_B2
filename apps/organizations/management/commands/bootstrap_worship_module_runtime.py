# apps/organizations/management/commands/bootstrap_worship_module_runtime.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.core.management.base import BaseCommand

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.models import OrganizationModuleActivation
from apps.organizations.modules.worship.services.bootstrap import bootstrap_worship_workspace


class Command(BaseCommand):
    help = "Initialize Worship module runtime for existing activations."

    def handle(self, *args, **options):
        activations = OrganizationModuleActivation.objects.filter(module__key=OrganizationModuleKey.WORSHIP).select_related("organization", "module")
        count = 0
        for activation in activations.iterator():
            bootstrap_worship_workspace(activation=activation, actor=None)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Initialized Worship runtime for {count} activation(s)."))
