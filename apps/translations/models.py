# apps/translations/models.py

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class TranslationCache(models.Model):
    """
    Stores cached translations for any text field
    across any model (Generic).
    """

    id = models.BigAutoField(primary_key=True)

    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        related_name="translation_caches",
    )
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey(
        "content_type",
        "object_id",
    )

    field_name = models.CharField(
        max_length=50,
        verbose_name="Source Field Name",
    )

    source_language = models.CharField(
        max_length=5,
        verbose_name="Detected Source Language",
    )
    target_language = models.CharField(
        max_length=5,
        verbose_name="Target Language",
    )

    source_text_hash = models.CharField(
        max_length=64,
        verbose_name="Hash of Source Text",
        help_text="Used for invalidation on content edit.",
    )

    translated_text = models.TextField(
        verbose_name="Translated Text",
    )

    engine = models.CharField(
        max_length=20,
        default="aws",
        db_index=True,
        help_text="aws | llm | aws+llm",
    )
    is_humanized = models.BooleanField(
        default=False,
        db_index=True,
        help_text="True if LLM improved tone/wording.",
    )
    llm_model = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Which LLM model produced the final text.",
    )
    prompt_version = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Prompt version for reproducibility.",
    )
    humanized_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When humanization was applied.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    last_accessed_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
    )

    def touch(self):
        self.last_accessed_at = timezone.now()
        self.save(
            update_fields=[
                "last_accessed_at"
            ]
        )

    class Meta:
        verbose_name = "Translation Cache"
        verbose_name_plural = "Translation Caches"

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "content_type",
                    "object_id",
                    "field_name",
                    "target_language",
                    "source_text_hash",
                ],
                name="uniq_translation_cache_entry",
            )
        ]

        indexes = [
            models.Index(
                fields=[
                    "content_type",
                    "object_id",
                ],
                name="translation_obj_idx",
            ),
            models.Index(
                fields=["target_language"],
                name="translation_target_lang_idx",
            ),
            models.Index(
                fields=["last_accessed_at"],
                name="translation_last_access_idx",
            ),
            models.Index(
                fields=["is_humanized"],
                name="translation_humanized_idx",
            ),
        ]

    def __str__(self):
        return (
            f"Translation<{self.content_type.app_label}."
            f"{self.content_type.model} "
            f"#{self.object_id} "
            f"{self.field_name} "
            f"{self.source_language}->{self.target_language}>"
        )


class ConversationKeyGuidance(models.Model):
    """
    Authoritative translatable guidance shown during the
    conversation-key backup and restore flow.
    """

    class Slug(models.TextChoices):
        BACKUP = (
            "backup",
            "Create recovery passphrase",
        )
        RESTORE = (
            "restore",
            "Restore encryption key",
        )
        RESOLVE = (
            "resolve",
            "Choose encryption setup option",
        )

    id = models.BigAutoField(
        primary_key=True
    )

    slug = models.CharField(
        max_length=32,
        choices=Slug.choices,
        unique=True,
        db_index=True,
    )

    title = models.CharField(
        max_length=160
    )

    content = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Conversation Key Guidance"
        verbose_name_plural = "Conversation Key Guidance"

    def __str__(self):
        return f"ConversationKeyGuidance<{self.slug}>"