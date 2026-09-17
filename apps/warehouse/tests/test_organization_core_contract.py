# apps/warehouse/tests/test_organization_core_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase

from apps.organizations.permissions import (
    OrganizationsEnabledPermission,
)
from apps.warehouse.views import (
    StockMovementViewSet,
    WarehouseInventoryViewSet,
    WarehouseViewSet,
)


class WarehouseOrganizationCoreContractTests(
    SimpleTestCase
):
    def test_warehouse_viewsets_use_organization_feature_gate(
        self,
    ):
        for viewset in (
            WarehouseViewSet,
            WarehouseInventoryViewSet,
            StockMovementViewSet,
        ):
            self.assertIn(
                OrganizationsEnabledPermission,
                viewset.permission_classes,
            )