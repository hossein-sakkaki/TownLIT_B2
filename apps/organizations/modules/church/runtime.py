# apps/organizations/modules/church/runtime.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.modules.runtime import OrganizationModuleRuntime
from apps.organizations.modules.church.services.bootstrap import bootstrap_church_workspace


runtime = OrganizationModuleRuntime(
    key=OrganizationModuleKey.CHURCH,
    initialize=bootstrap_church_workspace,
)
