# apps/posts/apps.py

from django.apps import AppConfig


class PostsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.posts"

    def ready(self):
        # -------------------------------------------------
        # Existing signal registrations (DO NOT TOUCH)
        # -------------------------------------------------
        from apps.posts.signals import moment_media_cleanup
        from apps.posts.signals import testimony_media_cleanup

        # -------------------------------------------------
        # Square registrations
        # -------------------------------------------------
        from apps.core.square.registry import (
            register_square_source,
            get_square_source,
            SquareContentSource,
        )

        from apps.posts.models.moment import Moment
        from apps.posts.models.testimony import Testimony

        # -----------------------------
        # Moment → Square
        # -----------------------------
        if get_square_source("moment") is None:
            register_square_source(
                source=SquareContentSource(
                    model=Moment,
                    kind="moment",
                    media_fields=["image", "video"],
                    requires_conversion=True,
                )
            )

        # -----------------------------
        # Testimony → Square
        # -----------------------------
        if get_square_source("testimony") is None:
            register_square_source(
                source=SquareContentSource(
                    model=Testimony,
                    kind="testimony",
                    media_fields=["video"],
                    requires_conversion=True,
                )
            )
