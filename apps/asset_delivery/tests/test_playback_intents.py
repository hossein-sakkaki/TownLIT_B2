#
#  apps/asset_delivery/tests/test_playback_intents.py
#  TownLIT-Backend
#
#  Created by Hossein Sakkaki on 2026-09-16.
#  Last Update by Hossein Sakkaki on 2026-09-16.
#

from django.test import SimpleTestCase

from apps.asset_delivery.constants import PlaybackIntent
from apps.asset_delivery.serializers import (
    PlaybackBatchItemSerializer,
    PlaybackURLSerializer,
)


class PlaybackIntentSerializerTests(SimpleTestCase):
    databases = set()

    def test_playback_url_serializer_accepts_every_canonical_intent(self):
        for intent in PlaybackIntent.ALL:
            with self.subTest(intent=intent):
                serializer = PlaybackURLSerializer(
                    data={
                        "url": "https://media.example.test/audio.mp3",
                        "expires_in": 300,
                        "kind": "audio",
                        "field_name": "audio_file",
                        "intent": intent,
                    }
                )

                self.assertTrue(
                    serializer.is_valid(),
                    serializer.errors,
                )

                self.assertEqual(
                    serializer.validated_data["intent"],
                    intent,
                )

    def test_batch_item_serializer_accepts_every_canonical_intent(self):
        for intent in PlaybackIntent.ALL:
            with self.subTest(intent=intent):
                serializer = PlaybackBatchItemSerializer(
                    data={
                        "app_label": "audio_catalog",
                        "model": "musictrackvariant",
                        "object_id": 1,
                        "field_name": "audio_file",
                        "kind": "audio",
                        "intent": intent,
                    }
                )

                self.assertTrue(
                    serializer.is_valid(),
                    serializer.errors,
                )

                self.assertEqual(
                    serializer.validated_data["intent"],
                    intent,
                )

    def test_playback_url_serializer_choices_match_canonical_intents(self):
        serializer = PlaybackURLSerializer()

        choices = set(
            serializer.fields["intent"].choices.keys()
        )

        self.assertEqual(
            choices,
            set(PlaybackIntent.ALL),
        )

    def test_batch_item_serializer_choices_match_canonical_intents(self):
        serializer = PlaybackBatchItemSerializer()

        choices = set(
            serializer.fields["intent"].choices.keys()
        )

        self.assertEqual(
            choices,
            set(PlaybackIntent.ALL),
        )

    def test_unknown_intent_is_rejected(self):
        serializer = PlaybackURLSerializer(
            data={
                "url": "https://media.example.test/audio.mp3",
                "expires_in": 300,
                "kind": "audio",
                "field_name": "audio_file",
                "intent": "unsupported-intent",
            }
        )

        self.assertFalse(
            serializer.is_valid()
        )

        self.assertIn(
            "intent",
            serializer.errors,
        )