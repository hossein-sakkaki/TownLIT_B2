# apps/organizations/modules/worship/runtime.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from apps.organizations.constants import OrganizationModuleKey
from apps.organizations.modules.runtime import OrganizationModuleRuntime
from apps.organizations.modules.worship.services.bootstrap import bootstrap_worship_workspace

runtime = OrganizationModuleRuntime(key=OrganizationModuleKey.WORSHIP, initialize=bootstrap_worship_workspace)
