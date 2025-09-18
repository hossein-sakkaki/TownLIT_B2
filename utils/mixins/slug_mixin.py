# Slug Mixin -----------------------------------------------------------------
from django.db import models, IntegrityError, transaction
from django.utils.text import slugify
from django.urls import reverse

class SlugMixin(models.Model):
    """
    Mixin to generate a unique, URL-friendly slug once per object.
    Keeps the slug stable on updates (unless manually changed).
    """
    slug = models.SlugField(
        max_length=140, unique=True, blank=True, null=True, db_index=True, verbose_name="Slug"
    )

    # Tuning knobs
    SLUG_MAX_LEN = 140
    SLUG_RETRY_LIMIT = 5  # safety net for rare race conditions

    class Meta:
        abstract = True

    def get_slug_source(self) -> str:
        """Child classes must return a human-readable string used to build the slug."""
        raise NotImplementedError("Subclasses should implement this!")

    def _build_base_slug(self) -> str:
        """Build base slug (truncated to max length) with a safe fallback."""
        base = slugify(self.get_slug_source() or "") or "item"
        return base[: self.SLUG_MAX_LEN]

    def _dedupe_slug(self, base: str) -> str:
        """
        Ensure uniqueness by appending -1, -2, ... if needed.
        Excludes current instance (important on updates).
        """
        Model = self.__class__
        candidate = base
        i = 1
        while Model.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            suffix = f"-{i}"
            candidate = f"{base[: self.SLUG_MAX_LEN - len(suffix)]}{suffix}"
            i += 1
        return candidate

    def save(self, *args, **kwargs):
        """
        Generate slug once if missing.
        Use a small retry loop to handle DB-level unique collisions under race.
        """
        if not self.slug:
            base = self._build_base_slug()
            self.slug = self._dedupe_slug(base)

        retries = 0
        while True:
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as e:
                # Retry only if it's likely the slug unique constraint
                if retries < self.SLUG_RETRY_LIMIT and "slug" in str(e).lower():
                    retries += 1
                    # Rebuild a new unique candidate and try again
                    base = (self.slug.rsplit("-", 1)[0]
                            if "-" in (self.slug or "")
                            else self._build_base_slug())
                    self.slug = self._dedupe_slug(base)
                    continue
                raise

    def get_absolute_url(self):
        """Reverse using slug if available; fallback to pk."""
        if not hasattr(self, "url_name"):
            raise NotImplementedError("Subclasses must define 'url_name' for reverse().")
        if self.slug:
            return reverse(self.url_name, kwargs={"slug": self.slug})
        return reverse(self.url_name, kwargs={"pk": self.pk})