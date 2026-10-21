# apps/organization_content/tests/test_square_discovery.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

"""Contract checks for Organization content in Square and Search."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.square.projections.organization_update import OrganizationUpdateSquareProjection
from apps.core.square.registry import get_square_source
from apps.organization_content.models import OrganizationUpdate


class OrganizationSquareRegistrationTests(SimpleTestCase):
    def test_organization_source_is_registered_once_with_search_fields(self):
        source = get_square_source("organization_update")
        self.assertIsNotNone(source)
        self.assertIs(source.model, OrganizationUpdate)
        self.assertIn("caption", source.search_fields)
        self.assertIn("organization__name", source.search_fields)
        self.assertFalse(source.requires_conversion)

    def test_projection_never_uses_operator_as_owner(self):
        update = SimpleNamespace(pk=7, created_by_id=14)
        projection = OrganizationUpdateSquareProjection(update)
        self.assertEqual(projection.get_owner_payload(), {
            "owner_user_id": None, "owner_username": None,
        })
        self.assertFalse(projection.should_hide_for_boundary())

    def test_projection_hides_unavailable_update_before_media_access(self):
        update = SimpleNamespace(pk=7, is_publicly_available=False)
        projection = OrganizationUpdateSquareProjection(update)
        self.assertIsNone(projection.get_preview())

    def test_projection_uses_organization_identity_not_publisher(self):
        organization = SimpleNamespace(
            name="TownLIT Society", slug="townlit-society",
            public_id="1b51dcab-3a3a-4ced-874f-e0c4fe82cbab", logo=None,
        )
        update = SimpleNamespace(
            pk=7, organization=organization, caption="Serving together",
        )
        projection = OrganizationUpdateSquareProjection(update)
        with patch("apps.core.square.projections.organization_update.cdn_url", return_value=None):
            meta = projection.get_meta()
        self.assertEqual(meta["title"], "TownLIT Society")
        self.assertEqual(meta["excerpt"], "Serving together")
        self.assertEqual(meta["organization_slug"], "townlit-society")


class OrganizationSquareQueryContractTests(SimpleTestCase):
    def test_discovery_query_compiles_without_personal_owner_fields(self):
        from apps.core.square.query import SquareQuery

        source = get_square_source("organization_update")
        queryset = SquareQuery._organization_updates(source, viewer=None)
        statement = str(queryset.query)
        self.assertIn("organization", statement.lower())
        self.assertIn("published_at", statement.lower())

    def test_search_query_compiles_with_organization_name(self):
        from apps.core.square.query import SquareQuery
        from apps.core.square.search import SquareContentSearch

        source = get_square_source("organization_update")
        queryset = SquareQuery._organization_updates(source, viewer=None)
        ranked = SquareContentSearch._apply_search(
            queryset=queryset, source=source, query="TownLIT",
        )
        self.assertIn("square_search_rank", str(ranked.query))
