# apps/audio_catalog/tests/test_track_credits.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

from django.test import SimpleTestCase

from apps.audio_catalog.models import AudioContributor, TrackContributor
from apps.audio_catalog.serializers.catalog import TrackCreditSerializer


class TrackCreditSerializerTests(SimpleTestCase):
    databases = set()

    def test_public_credit_contract_excludes_private_fields(self):
        contributor = AudioContributor(
            display_name="John Smith",
            legal_name="Private Legal Name",
            kind=AudioContributor.Kind.PERSON,
            external_reference="private-reference",
            metadata={"private": True},
        )

        credit = TrackContributor(
            contributor=contributor,
            role=TrackContributor.Role.COMPOSER,
            credit_text="Composed by John Smith",
            share_basis_points=5000,
            sort_order=10,
        )

        payload = TrackCreditSerializer(credit).data

        self.assertEqual(payload["contributor"]["display_name"], "John Smith")
        self.assertEqual(payload["contributor"]["kind"], "person")
        self.assertEqual(payload["role"], "composer")
        self.assertEqual(payload["credit_text"], "Composed by John Smith")
        self.assertEqual(payload["sort_order"], 10)

        self.assertNotIn("legal_name", payload["contributor"])
        self.assertNotIn("external_reference", payload["contributor"])
        self.assertNotIn("metadata", payload["contributor"])
        self.assertNotIn("share_basis_points", payload)