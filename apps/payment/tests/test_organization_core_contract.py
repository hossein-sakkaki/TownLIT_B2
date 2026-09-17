# apps/payment/tests/test_organization_core_contract.py
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
from apps.payment.models import Payment
from apps.payment.serializers import (
    PaymentAdvertisementSerializer,
    PaymentDonationSerializer,
    PaymentSubscriptionSerializer,
)


class PaymentOrganizationCoreContractTests(
    SimpleTestCase
):
    def test_payment_uses_organization_core(
        self,
    ):
        field = Payment._meta.get_field(
            "organization"
        )

        self.assertIs(
            field.remote_field.model,
            Organization,
        )

    def test_nested_payment_serializers_preserve_reference_contract(
        self,
    ):
        for serializer_class in (
            PaymentSubscriptionSerializer,
            PaymentAdvertisementSerializer,
            PaymentDonationSerializer,
        ):
            field = serializer_class().fields[
                "organization"
            ]

            self.assertIsInstance(
                field,
                OrganizationReferenceSerializer,
            )