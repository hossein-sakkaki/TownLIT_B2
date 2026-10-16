# apps/organizations/tests/test_discovery_ranking.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.
#

from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from apps.organizations.selectors.discovery import (
    OrganizationDiscoveryRankingPolicyV1,
)


class OrganizationDiscoveryRankingPolicyTests(
    SimpleTestCase
):
    def organization(self, **overrides):
        values = {
            "id": 1,
            "name": "TownLIT Community",
            "short_name": "TownLIT",
            "slug": "townlit-community",
            "activity_areas": [
                "Worship",
                "Education",
            ],
            "tagline": "A Christian community",
            "kind": "community",
            "city": "Coquitlam",
            "province_region": "BC",
            "country": "CA",
            "service_delivery_mode": "hybrid",
            "description": "Community programs and fellowship.",
            "logo": None,
            "thumbnail": None,
            "website_url": "https://example.org",
            "brand_color": "#3366CC",
            "updated_at": timezone.now(),
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_verified_organization_is_promoted_first(self):
        verified = self.organization(
            id=1,
            name="Verified Community",
        )
        unverified = self.organization(
            id=2,
            name="Unverified Community",
        )

        verified_key = (
            OrganizationDiscoveryRankingPolicyV1
            .sort_key(
                verified,
                normalized_query="community",
                is_verified=True,
            )
        )
        unverified_key = (
            OrganizationDiscoveryRankingPolicyV1
            .sort_key(
                unverified,
                normalized_query="community",
                is_verified=False,
            )
        )

        self.assertLess(
            verified_key,
            unverified_key,
        )

    def test_exact_name_match_beats_description_only_match(self):
        exact = self.organization(
            id=1,
            name="Hope Church",
            description="",
        )
        description_only = self.organization(
            id=2,
            name="Community Center",
            short_name="",
            slug="community-center",
            tagline="",
            activity_areas=[],
            kind="community",
            city="",
            province_region="",
            country="",
            service_delivery_mode="",
            description="Programs hosted with Hope Church.",
        )

        exact_score = (
            OrganizationDiscoveryRankingPolicyV1
            .text_relevance(
                exact,
                normalized_query="hope church",
            )
        )
        description_score = (
            OrganizationDiscoveryRankingPolicyV1
            .text_relevance(
                description_only,
                normalized_query="hope church",
            )
        )

        self.assertGreater(
            exact_score,
            description_score,
        )
