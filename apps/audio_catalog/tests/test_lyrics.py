# apps/audio_catalog/tests/test_lyrics.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import models
from django.test import SimpleTestCase

from apps.audio_catalog.models import (
    MusicLyrics,
    MusicLyricsLine,
    MusicTrack,
)
from apps.audio_catalog.services.lyrics import (
    published_lyrics_for_track,
    select_published_lyrics,
)


class _LinesStub:
    """
    Minimal reverse-relation stub used by lyrics service tests.
    """

    def __init__(self, *lines):
        self._lines = list(lines)

    def all(self):
        return list(self._lines)


class _LyricsQuerySetStub:
    """
    QuerySet-shaped iterable that performs no database access.
    """

    def __init__(self, documents):
        self.documents = list(documents)
        self.selected_related = ()
        self.prefetched_related = ()
        self.ordering = ()

    def select_related(self, *fields):
        self.selected_related = fields
        return self

    def prefetch_related(self, *fields):
        self.prefetched_related = fields
        return self

    def order_by(self, *fields):
        self.ordering = fields
        return self

    def __iter__(self):
        return iter(self.documents)


class MusicLyricsTests(SimpleTestCase):
    databases = set()

    def make_track(
        self,
        *,
        duration_ms: int = 180_000,
        language_code: str = "en",
    ) -> MusicTrack:
        return MusicTrack(
            id=101,
            catalog_id=201,
            title="Lyrics Test Track",
            duration_ms=duration_ms,
            language_code=language_code,
            is_instrumental=False,
            has_vocals=True,
        )

    def make_lyrics(
        self,
        *,
        track: MusicTrack | None = None,
        language_code: str = "en",
        kind: str = MusicLyrics.Kind.ORIGINAL,
        status: str = MusicLyrics.Status.DRAFT,
        timing_mode: str = MusicLyrics.TimingMode.PLAIN,
        plain_text: str = "",
        is_default: bool = False,
    ) -> MusicLyrics:
        resolved_track = track or self.make_track()

        return MusicLyrics(
            id=301,
            track=resolved_track,
            language_code=language_code,
            kind=kind,
            status=status,
            timing_mode=timing_mode,
            plain_text=plain_text,
            is_default=is_default,
        )

    # -------------------------------------------------
    # Document normalization / slots
    # -------------------------------------------------

    def test_language_code_is_normalized_without_database(self):
        self.assertEqual(
            MusicLyrics.normalize_language_code(
                "  EN_us  "
            ),
            "en-us",
        )

    def test_default_slot_is_mysql_safe_without_database(self):
        lyrics = self.make_lyrics(
            is_default=True,
        )

        changed = lyrics._sync_default_slot()

        self.assertTrue(changed)
        self.assertEqual(
            lyrics.default_slot,
            1,
        )

        lyrics.is_default = False

        changed = lyrics._sync_default_slot()

        self.assertTrue(changed)
        self.assertIsNone(
            lyrics.default_slot
        )

    def test_save_adds_default_slot_to_update_fields_without_database(
        self,
    ):
        lyrics = self.make_lyrics(
            is_default=True,
        )

        with patch.object(
            models.Model,
            "save",
            autospec=True,
            return_value=None,
        ) as model_save:
            lyrics.save(
                update_fields=[
                    "is_default",
                ],
            )

        self.assertEqual(
            lyrics.default_slot,
            1,
        )

        call = model_save.call_args

        self.assertIs(
            call.args[0],
            lyrics,
        )

        self.assertCountEqual(
            call.kwargs["update_fields"],
            [
                "is_default",
                "default_slot",
            ],
        )

    def test_published_save_sets_timestamp_without_database(self):
        lyrics = self.make_lyrics(
            status=MusicLyrics.Status.PUBLISHED,
        )

        self.assertIsNone(
            lyrics.published_at
        )

        with patch.object(
            models.Model,
            "save",
            autospec=True,
            return_value=None,
        ) as model_save:
            lyrics.save(
                update_fields=[
                    "status",
                ],
            )

        self.assertIsNotNone(
            lyrics.published_at
        )

        call = model_save.call_args

        self.assertCountEqual(
            call.kwargs["update_fields"],
            [
                "status",
                "published_at",
            ],
        )

    # -------------------------------------------------
    # Line validation
    # -------------------------------------------------

    def test_line_synchronized_document_requires_line_start(self):
        lyrics = self.make_lyrics(
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="First line",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Line-synchronized lyrics require a start time",
        ):
            line.clean()

    def test_line_end_requires_start(self):
        lyrics = self.make_lyrics(
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="First line",
            end_ms=3_000,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Lyrics line end time requires a start time",
        ):
            line.clean()

    def test_line_end_must_be_after_start(self):
        lyrics = self.make_lyrics(
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="First line",
            start_ms=3_000,
            end_ms=3_000,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Lyrics line end time must be after its start time",
        ):
            line.clean()

    def test_line_timing_cannot_exceed_track_duration(self):
        track = self.make_track(
            duration_ms=180_000,
        )

        lyrics = self.make_lyrics(
            track=track,
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="Late line",
            start_ms=180_001,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Lyrics line start time cannot exceed track duration",
        ):
            line.clean()

    def test_line_end_cannot_exceed_track_duration(self):
        track = self.make_track(
            duration_ms=180_000,
        )

        lyrics = self.make_lyrics(
            track=track,
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="Late ending line",
            start_ms=179_000,
            end_ms=180_001,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Lyrics line end time cannot exceed track duration",
        ):
            line.clean()

    def test_plain_document_rejects_synchronized_timing(self):
        lyrics = self.make_lyrics(
            timing_mode=MusicLyrics.TimingMode.PLAIN,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="Plain line",
            start_ms=1_000,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Plain lyrics cannot contain synchronized timing",
        ):
            line.clean()

    def test_line_text_is_trimmed(self):
        lyrics = self.make_lyrics(
            timing_mode=MusicLyrics.TimingMode.LINE,
        )

        line = MusicLyricsLine(
            lyrics=lyrics,
            sequence=0,
            text="  First line  ",
            start_ms=1_000,
        )

        line.clean()

        self.assertEqual(
            line.text,
            "First line",
        )

    # -------------------------------------------------
    # Selection policy
    # -------------------------------------------------

    def test_selector_prefers_requested_language(self):
        track = self.make_track(
            language_code="en",
        )

        original = self.make_lyrics(
            track=track,
            language_code="en",
            kind=MusicLyrics.Kind.ORIGINAL,
            status=MusicLyrics.Status.PUBLISHED,
            plain_text="English lyrics",
            is_default=True,
        )

        translation = self.make_lyrics(
            track=track,
            language_code="fa",
            kind=MusicLyrics.Kind.TRANSLATION,
            status=MusicLyrics.Status.PUBLISHED,
            plain_text="Persian lyrics",
        )

        selected = select_published_lyrics(
            [
                original,
                translation,
            ],
            track_language_code=(
                track.language_code
            ),
            language_code="fa",
        )

        self.assertIs(
            selected,
            translation,
        )

    def test_selector_prefers_exact_language_and_kind(self):
        track = self.make_track(
            language_code="en",
        )

        english = self.make_lyrics(
            track=track,
            language_code="en",
            kind=MusicLyrics.Kind.ORIGINAL,
            status=MusicLyrics.Status.PUBLISHED,
            is_default=True,
        )

        persian_translation = self.make_lyrics(
            track=track,
            language_code="fa",
            kind=MusicLyrics.Kind.TRANSLATION,
            status=MusicLyrics.Status.PUBLISHED,
        )

        persian_transliteration = self.make_lyrics(
            track=track,
            language_code="fa",
            kind=MusicLyrics.Kind.TRANSLITERATION,
            status=MusicLyrics.Status.PUBLISHED,
        )

        selected = select_published_lyrics(
            [
                english,
                persian_translation,
                persian_transliteration,
            ],
            track_language_code=(
                track.language_code
            ),
            language_code="fa",
            kind=MusicLyrics.Kind.TRANSLITERATION,
        )

        self.assertIs(
            selected,
            persian_transliteration,
        )

    def test_selector_falls_back_to_default_document(self):
        track = self.make_track(
            language_code="en",
        )

        default_document = self.make_lyrics(
            track=track,
            language_code="fa",
            kind=MusicLyrics.Kind.TRANSLATION,
            status=MusicLyrics.Status.PUBLISHED,
            is_default=True,
        )

        original = self.make_lyrics(
            track=track,
            language_code="en",
            kind=MusicLyrics.Kind.ORIGINAL,
            status=MusicLyrics.Status.PUBLISHED,
        )

        selected = select_published_lyrics(
            [
                default_document,
                original,
            ],
            track_language_code="en",
        )

        self.assertIs(
            selected,
            default_document,
        )

    def test_selector_returns_none_for_empty_collection(self):
        selected = select_published_lyrics(
            [],
            track_language_code="en",
        )

        self.assertIsNone(
            selected
        )

    # -------------------------------------------------
    # Published service
    # -------------------------------------------------

    def test_empty_published_document_is_not_exposed(self):
        document = SimpleNamespace(
            timing_mode=MusicLyrics.TimingMode.PLAIN,
            plain_text="",
            lines=_LinesStub(),
        )

        queryset = _LyricsQuerySetStub(
            [
                document,
            ]
        )

        track = self.make_track()

        with patch(
            "apps.audio_catalog.services.lyrics."
            "MusicLyrics.objects.filter",
            return_value=queryset,
        ) as filter_mock:
            documents = published_lyrics_for_track(
                track
            )

        self.assertEqual(
            documents,
            [],
        )

        filter_mock.assert_called_once_with(
            track=track,
            status=MusicLyrics.Status.PUBLISHED,
        )

        self.assertEqual(
            queryset.selected_related,
            (
                "track",
                "reference_variant",
                "rights_record",
            ),
        )

        self.assertEqual(
            queryset.prefetched_related,
            (
                "lines",
            ),
        )

    def test_plain_document_with_text_is_exposed(self):
        document = SimpleNamespace(
            timing_mode=MusicLyrics.TimingMode.PLAIN,
            plain_text="Plain lyrics",
            lines=_LinesStub(),
        )

        queryset = _LyricsQuerySetStub(
            [
                document,
            ]
        )

        with patch(
            "apps.audio_catalog.services.lyrics."
            "MusicLyrics.objects.filter",
            return_value=queryset,
        ):
            documents = published_lyrics_for_track(
                self.make_track()
            )

        self.assertEqual(
            documents,
            [
                document,
            ],
        )

    def test_synchronized_document_is_exposed(self):
        document = SimpleNamespace(
            timing_mode=MusicLyrics.TimingMode.LINE,
            plain_text="",
            lines=_LinesStub(
                SimpleNamespace(
                    text="First line",
                    start_ms=1_000,
                ),
                SimpleNamespace(
                    text="Second line",
                    start_ms=3_000,
                ),
            ),
        )

        queryset = _LyricsQuerySetStub(
            [
                document,
            ]
        )

        with patch(
            "apps.audio_catalog.services.lyrics."
            "MusicLyrics.objects.filter",
            return_value=queryset,
        ):
            documents = published_lyrics_for_track(
                self.make_track()
            )

        self.assertEqual(
            documents,
            [
                document,
            ],
        )

    def test_synchronized_document_without_start_time_is_hidden(
        self,
    ):
        document = SimpleNamespace(
            timing_mode=MusicLyrics.TimingMode.LINE,
            plain_text="",
            lines=_LinesStub(
                SimpleNamespace(
                    text="First line",
                    start_ms=1_000,
                ),
                SimpleNamespace(
                    text="Second line",
                    start_ms=None,
                ),
            ),
        )

        queryset = _LyricsQuerySetStub(
            [
                document,
            ]
        )

        with patch(
            "apps.audio_catalog.services.lyrics."
            "MusicLyrics.objects.filter",
            return_value=queryset,
        ):
            documents = published_lyrics_for_track(
                self.make_track()
            )

        self.assertEqual(
            documents,
            [],
        )