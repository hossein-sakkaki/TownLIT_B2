# utils/mixins/slug_mixin.py

from __future__ import annotations

from django.db import (
    IntegrityError,
    models,
    transaction,
)
from django.urls import reverse
from django.utils.text import slugify


class SlugMixin(models.Model):
    """
    Generate a unique and stable slug once per object.
    """

    slug = models.SlugField(
        max_length=140,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="Slug",
    )

    SLUG_MAX_LEN = 140
    SLUG_RETRY_LIMIT = 5
    SLUG_ALLOW_UNICODE = False

    class Meta:
        abstract = True

    def get_slug_source(self) -> str:
        """
        Return the human-readable slug source.
        """

        raise NotImplementedError(
            "Subclasses must implement get_slug_source()."
        )

    def _build_base_slug(self) -> str:
        """
        Build and normalize the base slug.
        """

        source = self.get_slug_source() or ""

        base = slugify(
            source,
            allow_unicode=self.SLUG_ALLOW_UNICODE,
        )

        if not base:
            base = "item"

        return base[: self.SLUG_MAX_LEN]

    def _dedupe_slug(self, base: str) -> str:
        """
        Add a numeric suffix when needed.
        """

        model_class = self.__class__
        candidate = base
        index = 1

        queryset = model_class._base_manager.all()

        while queryset.filter(
            slug=candidate,
        ).exclude(
            pk=self.pk,
        ).exists():
            suffix = f"-{index}"

            candidate = (
                f"{base[: self.SLUG_MAX_LEN - len(suffix)]}"
                f"{suffix}"
            )

            index += 1

        return candidate

    def save(self, *args, **kwargs):
        """
        Generate a slug once and retry rare collisions.
        """

        if not self.slug:
            base = self._build_base_slug()
            self.slug = self._dedupe_slug(base)

        retries = 0

        while True:
            try:
                with transaction.atomic():
                    return super().save(
                        *args,
                        **kwargs,
                    )

            except IntegrityError as exc:
                is_slug_collision = (
                    "slug"
                    in str(exc).lower()
                )

                if (
                    not is_slug_collision
                    or retries >= self.SLUG_RETRY_LIMIT
                ):
                    raise

                retries += 1

                base = self._build_base_slug()

                self.slug = self._dedupe_slug(
                    base
                )

    def get_absolute_url(self):
        """
        Resolve the object URL.
        """

        if not hasattr(self, "url_name"):
            raise NotImplementedError(
                "Subclasses must define url_name."
            )

        if self.slug:
            return reverse(
                self.url_name,
                kwargs={
                    "slug": self.slug,
                },
            )

        return reverse(
            self.url_name,
            kwargs={
                "pk": self.pk,
            },
        )