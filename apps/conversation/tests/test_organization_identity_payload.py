# apps/conversation/tests/test_organization_identity_payload.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-16.
# Last Update by Hossein Sakkaki on 2026-10-16.
#

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase

from apps.conversation.serializers.organization.context import (
    organization_identity_payload,
)


class OrganizationIdentityPayloadContractTests(SimpleTestCase):
    databases = set()

    def test_payload_exposes_avatar_resolution_identity(self):
        updated_at = datetime(
            2026,
            10,
            16,
            12,
            0,
            tzinfo=timezone.utc,
        )
        organization = SimpleNamespace(
            id=50,
            public_id=uuid4(),
            slug="townlit-society",
            name="TownLIT Society",
            short_name="TownLIT",
            brand_color=None,
            logo=None,
            thumbnail=None,
            updated_at=updated_at,
        )

        payload = organization_identity_payload(organization)

        self.assertEqual(payload["id"], 50)
        self.assertEqual(
            payload["public_id"],
            str(organization.public_id),
        )
        self.assertEqual(
            payload["updated_at"],
            updated_at.isoformat(),
        )
        self.assertIsNone(payload["avatar_url"])
        self.assertIsNone(payload["avatar_cdn_url"])
