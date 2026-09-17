# apps/audio_catalog/tests/test_lyrics_forced_aligner.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-16.
# Last Update by Hossein Sakkaki on 2026-09-16.

import math

from django.test import SimpleTestCase

from apps.audio_catalog.services.lyrics_forced_aligner import (
    _posterior_probability,
)


class LyricsForcedAlignerTests(
    SimpleTestCase
):
    databases = set()

    def test_zero_log_posterior_maps_to_probability_one(
        self,
    ):
        self.assertEqual(
            _posterior_probability(
                0.0
            ),
            1.0,
        )

    def test_log_posterior_maps_back_to_probability(
        self,
    ):
        self.assertAlmostEqual(
            _posterior_probability(
                math.log(
                    0.25
                )
            ),
            0.25,
            places=6,
        )

    def test_non_finite_log_posterior_fails_closed(
        self,
    ):
        self.assertEqual(
            _posterior_probability(
                float("-inf")
            ),
            0.0,
        )