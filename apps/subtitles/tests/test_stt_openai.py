# apps/subtitles/tests/test_stt_openai.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

from __future__ import annotations

import os
import tempfile

from unittest.mock import MagicMock, patch

from django.test import (
    SimpleTestCase,
    override_settings,
)

from apps.subtitles.services.stt_openai import (
    transcribe_audio,
)


@override_settings(
    OPENAI_API_KEY="test-openai-key",
    OPENAI_STT_MODEL="whisper-1",
)
class STTOpenAICompatibilityTests(
    SimpleTestCase
):
    databases = set()

    def _audio_path(
        self,
    ) -> str:
        handle = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        )

        handle.write(
            b"RIFF-townlit-test-audio"
        )
        handle.flush()
        handle.close()

        self.addCleanup(
            self._remove_file,
            handle.name,
        )

        return handle.name

    @staticmethod
    def _remove_file(
        path: str,
    ) -> None:
        try:
            os.unlink(
                path
            )
        except FileNotFoundError:
            pass

    @staticmethod
    def _client(
        openai_class,
        *,
        response: dict,
    ):
        client = MagicMock()

        openai_class.return_value = (
            client
        )

        (
            client
            .audio
            .transcriptions
            .create
            .return_value
        ) = response

        return client

    @patch(
        "apps.subtitles.services."
        "stt_openai.OpenAI"
    )
    def test_legacy_path_preserves_original_request_shape(
        self,
        openai_class,
    ):
        path = self._audio_path()

        segments = [
            {
                "start": 0.0,
                "end": 1.0,
                "text": "Hello TownLIT",
            },
        ]

        client = self._client(
            openai_class,
            response={
                "language": "en",
                "text": "Hello TownLIT",
                "segments": segments,
            },
        )

        result = transcribe_audio(
            wav_path=path,
        )

        openai_class.assert_called_once_with(
            api_key="test-openai-key",
        )

        (
            client
            .audio
            .transcriptions
            .create
            .assert_called_once()
        )

        kwargs = (
            client
            .audio
            .transcriptions
            .create
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["model"],
            "whisper-1",
        )

        self.assertEqual(
            kwargs["response_format"],
            "verbose_json",
        )

        self.assertIsNone(
            kwargs["language"]
        )

        self.assertIn(
            "file",
            kwargs,
        )

        self.assertNotIn(
            "prompt",
            kwargs,
        )

        self.assertNotIn(
            "timestamp_granularities",
            kwargs,
        )

        self.assertEqual(
            set(
                result.keys()
            ),
            {
                "language",
                "text",
                "segments",
                "model",
            },
        )

        self.assertEqual(
            result["language"],
            "en",
        )

        self.assertEqual(
            result["text"],
            "Hello TownLIT",
        )

        self.assertEqual(
            result["segments"],
            segments,
        )

        self.assertEqual(
            result["model"],
            "whisper-1",
        )

    @patch(
        "apps.subtitles.services."
        "stt_openai.OpenAI"
    )
    def test_legacy_language_parameter_is_preserved(
        self,
        openai_class,
    ):
        path = self._audio_path()

        client = self._client(
            openai_class,
            response={
                "language": "fa",
                "text": "سلام",
                "segments": [],
            },
        )

        result = transcribe_audio(
            wav_path=path,
            language="fa",
        )

        kwargs = (
            client
            .audio
            .transcriptions
            .create
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["language"],
            "fa",
        )

        self.assertNotIn(
            "timestamp_granularities",
            kwargs,
        )

        self.assertNotIn(
            "prompt",
            kwargs,
        )

        self.assertNotIn(
            "words",
            result,
        )

    @patch(
        "apps.subtitles.services."
        "stt_openai.OpenAI"
    )
    def test_word_timestamps_are_opt_in(
        self,
        openai_class,
    ):
        path = self._audio_path()

        words = [
            {
                "word": "Show",
                "start": 10.0,
                "end": 10.3,
            },
            {
                "word": "me",
                "start": 10.3,
                "end": 10.5,
            },
        ]

        client = self._client(
            openai_class,
            response={
                "language": "en",
                "text": "Show me",
                "segments": [
                    {
                        "start": 10.0,
                        "end": 10.5,
                        "text": "Show me",
                    },
                ],
                "words": words,
            },
        )

        result = transcribe_audio(
            wav_path=path,
            language="en",
            prompt=(
                "Show me a sign "
                "of Your goodness"
            ),
            include_word_timestamps=True,
        )

        kwargs = (
            client
            .audio
            .transcriptions
            .create
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["model"],
            "whisper-1",
        )

        self.assertEqual(
            kwargs["response_format"],
            "verbose_json",
        )

        self.assertEqual(
            kwargs["language"],
            "en",
        )

        self.assertEqual(
            kwargs["prompt"],
            (
                "Show me a sign "
                "of Your goodness"
            ),
        )

        self.assertEqual(
            kwargs[
                "timestamp_granularities"
            ],
            [
                "word",
                "segment",
            ],
        )

        self.assertEqual(
            result["words"],
            words,
        )

        self.assertEqual(
            result["model"],
            "whisper-1",
        )

    @patch(
        "apps.subtitles.services."
        "stt_openai.OpenAI"
    )
    def test_prompt_only_does_not_enable_word_timestamps(
        self,
        openai_class,
    ):
        path = self._audio_path()

        client = self._client(
            openai_class,
            response={
                "language": "en",
                "text": "Hello",
                "segments": [],
            },
        )

        result = transcribe_audio(
            wav_path=path,
            prompt="TownLIT",
        )

        kwargs = (
            client
            .audio
            .transcriptions
            .create
            .call_args
            .kwargs
        )

        self.assertEqual(
            kwargs["prompt"],
            "TownLIT",
        )

        self.assertNotIn(
            "timestamp_granularities",
            kwargs,
        )

        self.assertNotIn(
            "words",
            result,
        )