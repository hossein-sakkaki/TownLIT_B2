# apps/posts/apps.py

from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = (
        "django.db.models.BigAutoField"
    )

    name = "apps.posts"

    def ready(self):
        # -------------------------------------------------
        # Media cleanup signals
        # -------------------------------------------------
        from apps.posts.signals import (
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

        # Journey is intentionally not registered in Square.