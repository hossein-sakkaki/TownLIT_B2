# apps/content_safety/services/providers/openai_moderation.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-14.

from __future__ import annotations

from django.conf import settings
from openai import OpenAI

from apps.content_safety.services.types import (
    ProviderModerationResult,
)


class OpenAIModerationProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        model: str | None = None,
    ):
        self.model = (
            model
            or settings.CONTENT_SAFETY_MODERATION_MODEL
        )

        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=(
                settings.CONTENT_SAFETY_OPENAI_TIMEOUT_SECONDS
            ),
            max_retries=(
                settings.CONTENT_SAFETY_OPENAI_MAX_RETRIES
            ),
        )

    def moderate_text(
        self,
        *,
        text: str,
    ) -> ProviderModerationResult:
        """
        Moderate one text input.
        """

        return self._moderate(
            input_payload=text
        )

    def moderate_image_data_url(
        self,
        *,
        image_data_url: str,
    ) -> ProviderModerationResult:
        """
        Moderate one image using a private Base64 data URL.
        """

        normalized = str(
            image_data_url
            or ""
        ).strip()

        if not normalized:
            raise ValueError(
                "Image data URL is required."
            )

        return self._moderate(
            input_payload=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": normalized,
                    },
                },
            ]
        )

    def _moderate(
        self,
        *,
        input_payload,
    ) -> ProviderModerationResult:
        """
        Execute one OpenAI moderation request.
        """

        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "OPENAI_API_KEY is missing."
            )

        response = self.client.moderations.create(
            model=self.model,
            input=input_payload,
        )

        if not response.results:
            raise RuntimeError(
                "Moderation returned no results."
            )

        result = response.results[
            0
        ]

        payload = result.model_dump(
            by_alias=True
        )

        categories = {
            str(key): bool(value)
            for key, value in (
                payload.get(
                    "categories"
                )
                or {}
            ).items()
        }

        scores = {
            str(key): float(value)
            for key, value in (
                payload.get(
                    "category_scores"
                )
                or {}
            ).items()
        }

        applied_input_types = {
            str(key): [
                str(item)
                for item in (
                    value or []
                )
            ]
            for key, value in (
                payload.get(
                    "category_applied_input_types"
                )
                or {}
            ).items()
        }

        return ProviderModerationResult(
            flagged=bool(
                payload.get(
                    "flagged",
                    False,
                )
            ),
            categories=categories,
            category_scores=scores,
            applied_input_types=applied_input_types,
            provider=self.provider_name,
            model=str(
                getattr(
                    response,
                    "model",
                    None,
                )
                or self.model
            ),
            response_id=str(
                getattr(
                    response,
                    "id",
                    None,
                )
                or ""
            ),
            cached=False,
        )