# apps/posts/apps.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-31.
# Last Update by Hossein Sakkaki on 2026-08-31.
#

from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = "apps.posts"

    def ready(self):
        # Register the Phase 8A content model without replacing
        # the existing posts/models/__init__.py surface.
        from apps.posts.models import church_teaching as church_teaching_models

        # -------------------------------------------------
        # Media cleanup signals
        # -------------------------------------------------
        from apps.posts.signals import (
            church_teaching_media_cleanup,
            journey_media_cleanup,
            moment_media_cleanup,
            prayer_media_cleanup,
            testimony_media_cleanup,
        )

        # -------------------------------------------------
        # Existing trust signals
        # -------------------------------------------------
        from apps.posts.signals import (
            townlit_activity_signals,
            trust_activity_signals,
        )

        # Keep imports explicit so Django retains signal registration.
        _ = (
            church_teaching_models,
            church_teaching_media_cleanup,
            journey_media_cleanup,
            moment_media_cleanup,
            prayer_media_cleanup,
            testimony_media_cleanup,
            townlit_activity_signals,
            trust_activity_signals,
        )

        # -------------------------------------------------
        # Existing Square registrations
        # -------------------------------------------------
        from apps.core.square.registry import (
            SquareContentSource,
            get_square_source,
            register_square_source,
        )

        from apps.posts.models.moment import (
            Moment,
        )
        from apps.posts.models.pray import (
            Prayer,
        )
        from apps.posts.models.testimony import (
            Testimony,
        )

        if get_square_source("moment") is None:
            register_square_source(
                source=SquareContentSource(
                    model=Moment,
                    kind="moment",
                    media_fields=[
                        "image",
                        "video",
                    ],
                    requires_conversion=True,
                )
            )

        if get_square_source(
            "testimony"
        ) is None:
            register_square_source(
                source=SquareContentSource(
                    model=Testimony,
                    kind="testimony",
                    media_fields=[
                        "video",
                    ],
                    requires_conversion=True,
                )
            )

        if get_square_source("pray") is None:
            register_square_source(
                source=SquareContentSource(
                    model=Prayer,
                    kind="pray",
                    media_fields=[
                        "image",
                        "video",
                    ],
                    requires_conversion=True,
                )
            )

        # Journey and Church teaching are intentionally not registered in Square.
