# apps/subtitles/tests/test_track_access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-09.
# Last Update by Hossein Sakkaki on 2026-11-09.

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from rest_framework.exceptions import MethodNotAllowed, NotFound, ValidationError

from apps.subtitles.models import SubtitleJobStatus, TranscriptJobStatus
from apps.subtitles.services.access import can_view_transcript
from apps.subtitles.views import (
    SubtitleTrackViewSet,
    VoiceTrackViewSet,
    _parse_positive_id,
    _true,
)


class _FakeMoment:
    objects = MagicMock()

    def __init__(self, **overrides):
        values = {
            "pk": 41,
            "_meta": SimpleNamespace(label_lower="posts.moment"),
            "is_active": True,
            "is_hidden": False,
            "is_suspended": False,
            "is_converted": True,
            "video": "video/master.m3u8",
        }
        values.update(overrides)
        self.__dict__.update(values)


def _transcript(target, status=TranscriptJobStatus.DONE):
    return SimpleNamespace(pk=9, status=status, content_object=target)


class TranscriptAuthorizationTests(SimpleTestCase):
    def setUp(self):
        self.viewer = SimpleNamespace(is_authenticated=True)

    def test_missing_or_unready_transcript_is_denied(self):
        self.assertFalse(can_view_transcript(transcript=None, viewer=self.viewer))
        self.assertFalse(can_view_transcript(
            transcript=_transcript(_FakeMoment(), status=TranscriptJobStatus.PENDING),
            viewer=self.viewer,
        ))

    def test_unsupported_source_type_is_denied(self):
        unknown = SimpleNamespace(
            pk=42,
            _meta=SimpleNamespace(label_lower="private.secret"),
        )
        self.assertFalse(can_view_transcript(
            transcript=_transcript(unknown), viewer=self.viewer,
        ))

    def test_hidden_source_is_denied_before_policy_query(self):
        with patch("apps.subtitles.services.access.VisibilityQuery.for_viewer") as policy:
            allowed = can_view_transcript(
                transcript=_transcript(_FakeMoment(is_hidden=True)),
                viewer=self.viewer,
            )
        self.assertFalse(allowed)
        policy.assert_not_called()

    @patch("apps.subtitles.services.access.held_representation_or_none")
    @patch("apps.subtitles.services.access.VisibilityPolicy.gate_reason")
    @patch("apps.subtitles.services.access.BoundaryVisibilityQuery.exclude_boundary_conflicts")
    @patch("apps.subtitles.services.access.VisibilityQuery.for_viewer")
    def test_source_policy_boundary_and_hold_are_required(
        self, visibility, boundary, gate, held
    ):
        visible = MagicMock()
        visible.exists.return_value = True
        visibility.return_value = visible
        boundary.return_value = visible
        gate.return_value = None
        held.return_value = {"id": 41}
        target = _FakeMoment()

        self.assertTrue(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))
        gate.return_value = "restricted"
        self.assertFalse(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))
        gate.return_value = None
        held.return_value = None
        self.assertFalse(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))
        boundary.return_value.exists.return_value = False
        self.assertFalse(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))

    @patch("apps.subtitles.services.access.VisibilityQuery.for_viewer")
    def test_access_system_failure_fails_closed(self, visibility):
        visibility.side_effect = RuntimeError("visibility offline")
        self.assertFalse(can_view_transcript(
            transcript=_transcript(_FakeMoment()), viewer=self.viewer,
        ))

    @patch("apps.subtitles.services.access.can_view_organization_content")
    def test_published_organization_video_uses_organization_access(self, org_access):
        org_access.return_value = True
        target = SimpleNamespace(
            pk=78,
            _meta=SimpleNamespace(
                label_lower="organization_media.churchteachingcontent"
            ),
            status="published",
            content_format="video",
            is_converted=True,
            video="master.m3u8",
            organization=SimpleNamespace(pk=3),
        )
        self.assertTrue(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))
        target.status = "draft"
        self.assertFalse(can_view_transcript(
            transcript=_transcript(target), viewer=self.viewer,
        ))


class TrackEndpointTests(SimpleTestCase):
    def test_unbounded_list_is_rejected(self):
        with self.assertRaises(MethodNotAllowed):
            SubtitleTrackViewSet().list(SimpleNamespace(user=None))
        with self.assertRaises(MethodNotAllowed):
            VoiceTrackViewSet().list(SimpleNamespace(user=None))

    @patch("rest_framework.viewsets.ReadOnlyModelViewSet.get_object")
    @patch("apps.subtitles.views.can_view_transcript")
    def test_track_detail_cannot_bypass_transcript_access(self, can_view, super_get):
        super_get.return_value = SimpleNamespace(transcript=_transcript(_FakeMoment()))
        can_view.return_value = False
        view = SubtitleTrackViewSet()
        view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        with self.assertRaises(NotFound):
            view.get_object()
        view = VoiceTrackViewSet()
        view.request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        with self.assertRaises(NotFound):
            view.get_object()

    @patch("apps.subtitles.views.get_object_or_404")
    @patch("apps.subtitles.views.can_view_transcript", return_value=False)
    def test_by_transcript_denies_private_content_before_listing(self, denied, lookup):
        lookup.return_value = _transcript(_FakeMoment())
        view = SubtitleTrackViewSet()
        with self.assertRaises(NotFound):
            view.by_transcript(
                SimpleNamespace(user=SimpleNamespace(is_authenticated=True)),
                transcript_id="9",
            )

    def test_successful_content_response_is_non_cacheable(self):
        view = SubtitleTrackViewSet()
        view.get_object = lambda: SimpleNamespace(
            status=SubtitleJobStatus.DONE,
            content="WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi",
            fmt="vtt",
        )
        response = view.content(SimpleNamespace(user=None))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("Authorization", response["Vary"])

    def test_invalid_identifier_and_explicit_boolean(self):
        with self.assertRaises(ValidationError):
            _parse_positive_id("bad", field="transcript_id")
        self.assertFalse(_true("false"))
        self.assertTrue(_true("true"))


class EnsureIdempotencyTests(TestCase):
    @patch("apps.subtitles.tasks.generate_subtitles_task.delay")
    def test_pending_subtitle_is_queued_only_once(self, enqueue):
        from django.contrib.contenttypes.models import ContentType
        from apps.posts.models.testimony import Testimony
        from apps.subtitles.models import VideoTranscript
        from apps.subtitles.services.ensure import ensure_subtitle_track

        transcript = VideoTranscript.objects.create(
            content_type=ContentType.objects.get_for_model(Testimony),
            object_id=987654,
            status=TranscriptJobStatus.DONE,
            source_language="en",
        )
        with self.captureOnCommitCallbacks(execute=True):
            first = ensure_subtitle_track(
                transcript=transcript, target_language="fr"
            )
            again = ensure_subtitle_track(
                transcript=transcript, target_language="fr"
            )

        self.assertEqual(first.pk, again.pk)
        enqueue.assert_called_once_with(
            transcript_id=transcript.pk,
            target_language="fr",
            fmt="vtt",
        )
