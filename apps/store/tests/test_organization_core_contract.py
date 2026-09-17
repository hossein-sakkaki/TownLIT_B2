# apps/store/tests/test_organization_core_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase

from apps.organizations.models import Organization
from apps.organizations.serializers import (
    OrganizationReferenceSerializer,
)
from apps.store.models import Store
from apps.store.serializers import StoreSerializer


class StoreOrganizationCoreContractTests(
    SimpleTestCase
):
    def test_store_uses_organization_core(
        self,
    ):
        field = Store._meta.get_field(
            "organization"
        )

        self.assertIs(
            field.remote_field.model,
            Organization,
        )

    def test_store_preserves_reference_serializer_contract(
        self,
    ):
        field = StoreSerializer._declared_fields[
            "organization"
        ]

        self.assertIsInstance(
            field,
            OrganizationReferenceSerializer,
        )