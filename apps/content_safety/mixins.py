# apps/content_safety/mixins.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-25.
# Last Update by Hossein Sakkaki on 2026-08-25.

from __future__ import annotations

import logging

from django.contrib.contenttypes.fields import (
    GenericRelation,
)
from django.db import models


logger = logging.getLogger(
    __name__
)


class ContentSafetyMediaTargetMixin(
    models.Model
):
    """
    Opt-in model integration for asynchronous media Content Safety.

    Models declare only `content_safety_media_config`.

    Content Safety remains independent from Media Conversion while
    participating in MediaConversionMixin's per-field enqueue gate.
    """

    content_safety_jobs = GenericRelation(
        "content_safety.ContentSafetyJob",
        content_type_field="content_type",
        object_id_field="object_id",
    )

    content_safety_media_config = {}

    class Meta:
        abstract = True

    def get_content_safety_media_config(
        self,
    ) -> dict:
        config = getattr(
            self,
            "content_safety_media_config",
            None,
        )

        if not isinstance(
            config,
            dict,
        ):
            return {}

        return config

    def media_conversion_enqueue_allowed(
        self,
        *,
        field_name: str,
        kind: str,
        source_path: str,
    ) -> bool:
        """
        Participate in MediaConversionMixin's field-level enqueue gate.
        """

        parent = getattr(
            super(),
            "media_conversion_enqueue_allowed",
            None,
        )

        if callable(
            parent
        ):
            parent_allowed = parent(
                field_name=field_name,
                kind=kind,
                source_path=source_path,
            )

            if not parent_allowed:
                return False

        from apps.content_safety.services.media_jobs import (
            content_safety_allows_conversion_for_source,
        )

        try:
            return (
                content_safety_allows_conversion_for_source(
                    instance=self,
                    field_name=field_name,
                    kind=kind,
                    source_path=source_path,
                )
            )

        except Exception:
            logger.exception(
                (
                    "Content Safety conversion gate failed "
                    "for %s[%s].%s"
                ),
                self.__class__.__name__,
                getattr(
                    self,
                    "pk",
                    None,
                ),
                field_name,
            )

            # Fail closed for a configured safety-gated field.
            return False

    def get_media_content_safety_gate(
        self,
        *,
        field_name: str,
    ):
        """
        Optional serializer-facing bridge.

        Media Conversion serializers do not import Content Safety directly.
        """

        from apps.content_safety.services.media_jobs import (
            resolve_content_safety_serializer_state,
        )

        return (
            resolve_content_safety_serializer_state(
                instance=self,
                field_name=field_name,
            )
        )