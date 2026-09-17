# apps/posts/tests/test_testimony_organization_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.test import SimpleTestCase

from apps.organizations.models import Organization
from apps.posts.models.testimony import Testimony


class TestimonyOrganizationContractTests(
    SimpleTestCase
):
    def test_org_tags_use_organization_core(self):
        field = Testimony._meta.get_field(
            "org_tags"
        )

        self.assertIs(
            field.remote_field.model,
            Organization,
        )

    def test_org_tags_field_name_remains_stable(self):
        field = Testimony._meta.get_field(
            "org_tags"
        )

        self.assertEqual(
            field.name,
            "org_tags",
        )

    def test_org_tags_reverse_name_remains_stable(self):
        field = Testimony._meta.get_field(
            "org_tags"
        )

        self.assertEqual(
            field.remote_field.related_name,
            "tagged_in_testimonies",
        )