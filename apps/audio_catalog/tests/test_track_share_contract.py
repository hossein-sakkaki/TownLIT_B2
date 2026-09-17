# apps/audio_catalog/tests/test_track_share_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from django.test import SimpleTestCase

from apps.audio_catalog.models import AudioCatalog
from apps.audio_catalog.serializers.catalog import (
    TrackDetailSerializer,
    TrackListSerializer,
    TrackShareReferenceSerializer,
    track_share_reference,
)


class MusicTrackShareContractTests(
    SimpleTestCase
):
    """
    Pure unit coverage for the music-track share contract.

    These tests intentionally do not touch the database.
    """

    def make_track(
        self,
        *,
        visibility: str,
        public_id: UUID | None = None,
        slug: str = "example-track",
    ):
        return SimpleNamespace(
            public_id=public_id or uuid4(),
            slug=slug,
            catalog=SimpleNamespace(
                visibility=visibility
            ),
        )

    def test_authenticated_catalog_track_has_share_reference(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.AUTHENTICATED
            )
        )

        share = track_share_reference(
            track
        )

        self.assertEqual(
            share,
            {
                "kind": "music_track",
                "canonical_path":
                    f"/music/{track.public_id}",
            },
        )

    def test_public_catalog_track_has_share_reference(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.PUBLIC
            )
        )

        share = track_share_reference(
            track
        )

        self.assertEqual(
            share,
            {
                "kind": "music_track",
                "canonical_path":
                    f"/music/{track.public_id}",
            },
        )

    def test_private_catalog_track_is_not_shareable(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.PRIVATE
            )
        )

        self.assertIsNone(
            track_share_reference(
                track
            )
        )

    def test_share_path_uses_public_id_not_slug(
        self,
    ):
        track_id = uuid4()

        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.AUTHENTICATED
            ),
            public_id=track_id,
            slug="this-slug-may-change",
        )

        share = track_share_reference(
            track
        )

        self.assertIsNotNone(
            share
        )

        self.assertEqual(
            share["canonical_path"],
            f"/music/{track_id}",
        )

        self.assertNotEqual(
            share["canonical_path"],
            f"/music/{track.slug}",
        )

    def test_share_reference_contains_routing_metadata_only(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.AUTHENTICATED
            )
        )

        payload = track_share_reference(
            track
        )

        self.assertIsNotNone(
            payload
        )

        serialized = (
            TrackShareReferenceSerializer(
                instance=payload
            )
            .data
        )

        self.assertEqual(
            set(serialized.keys()),
            {
                "kind",
                "canonical_path",
            },
        )

        self.assertNotIn(
            "playback",
            serialized,
        )

        self.assertNotIn(
            "asset",
            serialized,
        )

        self.assertNotIn(
            "rights",
            serialized,
        )

        self.assertNotIn(
            "url",
            serialized,
        )

    def test_list_serializer_exposes_share_contract(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.AUTHENTICATED
            )
        )

        serializer = (
            TrackListSerializer()
        )

        self.assertIn(
            "share",
            serializer.fields,
        )

        self.assertEqual(
            serializer.get_share(
                track
            ),
            {
                "kind": "music_track",
                "canonical_path":
                    f"/music/{track.public_id}",
            },
        )

    def test_detail_serializer_inherits_same_share_contract(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.PUBLIC
            )
        )

        list_share = (
            TrackListSerializer()
            .get_share(
                track
            )
        )

        detail_share = (
            TrackDetailSerializer()
            .get_share(
                track
            )
        )

        self.assertEqual(
            list_share,
            detail_share,
        )

    def test_private_track_serializer_share_is_null(
        self,
    ):
        track = self.make_track(
            visibility=(
                AudioCatalog.Visibility.PRIVATE
            )
        )

        self.assertIsNone(
            TrackListSerializer()
            .get_share(
                track
            )
        )