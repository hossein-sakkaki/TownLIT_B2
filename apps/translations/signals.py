# apps/translations/signals.py

from __future__ import annotations

from typing import Iterable

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.testimony import Testimony
from apps.profiles.models.member import Member
from apps.translations.models import (
    ConversationKeyGuidance,
    TranslationCache,
)


# =============================================================================
# Shared helpers
# =============================================================================

def _content_type_for_instance(instance) -> ContentType:
    """
    Return the concrete content type used by TranslationCache.
    """
    return ContentType.objects.get_for_model(
        instance,
        for_concrete_model=True,
    )


def _delete_translations_for_instance(instance) -> int:
    """
    Delete every cached translation belonging to one model instance.

    This is required because GenericForeignKey does not provide a database-level
    cascade from the translated object to TranslationCache.
    """
    if not getattr(instance, "pk", None):
        return 0

    content_type = _content_type_for_instance(instance)

    deleted_count, _ = TranslationCache.objects.filter(
        content_type=content_type,
        object_id=instance.pk,
    ).delete()

    return deleted_count


def _delete_translation_fields_for_instance(
    instance,
    field_names: Iterable[str],
) -> int:
    """
    Delete cached translations only for selected fields of one instance.
    """
    if not getattr(instance, "pk", None):
        return 0

    normalized_fields = {
        str(field_name).strip()
        for field_name in field_names
        if str(field_name).strip()
    }

    if not normalized_fields:
        return 0

    content_type = _content_type_for_instance(instance)

    deleted_count, _ = TranslationCache.objects.filter(
        content_type=content_type,
        object_id=instance.pk,
        field_name__in=normalized_fields,
    ).delete()

    return deleted_count


def _normalized_text(value) -> str:
    """
    Normalize nullable text values for reliable change detection.

    Whitespace inside the text is preserved. Only None is normalized to an
    empty string because None and an empty database value both represent no
    translatable content here.
    """
    if value is None:
        return ""

    return str(value)


def _capture_changed_translation_fields(
    *,
    instance,
    model,
    tracked_fields: tuple[str, ...],
    attribute_name: str,
) -> None:
    """
    Compare the persisted row with the value about to be saved.

    The resulting changed-field set is temporarily attached to the instance and
    consumed by the corresponding post_save receiver.
    """
    setattr(
        instance,
        attribute_name,
        set(),
    )

    if not getattr(instance, "pk", None):
        return

    previous = (
        model.objects
        .filter(pk=instance.pk)
        .values(*tracked_fields)
        .first()
    )

    if previous is None:
        return

    changed_fields: set[str] = set()

    for field_name in tracked_fields:
        previous_value = _normalized_text(
            previous.get(field_name)
        )
        incoming_value = _normalized_text(
            getattr(instance, field_name, None)
        )

        if previous_value != incoming_value:
            changed_fields.add(field_name)

    setattr(
        instance,
        attribute_name,
        changed_fields,
    )


def _consume_changed_translation_fields(
    *,
    instance,
    attribute_name: str,
) -> set[str]:
    """
    Read and remove a temporary changed-field set from a saved instance.
    """
    changed_fields = set(
        getattr(
            instance,
            attribute_name,
            set(),
        )
    )

    if hasattr(instance, attribute_name):
        delattr(
            instance,
            attribute_name,
        )

    return changed_fields


# =============================================================================
# Post content deletion
# =============================================================================

@receiver(
    post_delete,
    sender=Testimony,
    dispatch_uid="translations.delete_testimony_cache",
)
def delete_testimony_translations(
    sender,
    instance,
    **kwargs,
):
    _delete_translations_for_instance(
        instance
    )


@receiver(
    post_delete,
    sender=Moment,
    dispatch_uid="translations.delete_moment_cache",
)
def delete_moment_translations(
    sender,
    instance,
    **kwargs,
):
    _delete_translations_for_instance(
        instance
    )


@receiver(
    post_delete,
    sender=Prayer,
    dispatch_uid="translations.delete_prayer_cache",
)
def delete_prayer_translations(
    sender,
    instance,
    **kwargs,
):
    _delete_translations_for_instance(
        instance
    )


# =============================================================================
# Member biography / vision invalidation
# =============================================================================

_MEMBER_CHANGED_FIELDS_ATTRIBUTE = (
    "_translation_cache_changed_member_fields"
)

_MEMBER_TRANSLATABLE_FIELDS = (
    "biography",
    "vision",
)


@receiver(
    pre_save,
    sender=Member,
    dispatch_uid="translations.capture_member_translation_changes",
)
def capture_member_translation_changes(
    sender,
    instance,
    raw=False,
    **kwargs,
):
    if raw:
        return

    _capture_changed_translation_fields(
        instance=instance,
        model=Member,
        tracked_fields=_MEMBER_TRANSLATABLE_FIELDS,
        attribute_name=_MEMBER_CHANGED_FIELDS_ATTRIBUTE,
    )


@receiver(
    post_save,
    sender=Member,
    dispatch_uid="translations.invalidate_changed_member_fields",
)
def invalidate_changed_member_translation_fields(
    sender,
    instance,
    created,
    raw=False,
    **kwargs,
):
    if raw:
        return

    changed_fields = (
        _consume_changed_translation_fields(
            instance=instance,
            attribute_name=(
                _MEMBER_CHANGED_FIELDS_ATTRIBUTE
            ),
        )
    )

    if created or not changed_fields:
        return

    _delete_translation_fields_for_instance(
        instance,
        changed_fields,
    )


@receiver(
    post_delete,
    sender=Member,
    dispatch_uid="translations.delete_member_cache",
)
def delete_member_translations(
    sender,
    instance,
    **kwargs,
):
    _delete_translations_for_instance(
        instance
    )


# =============================================================================
# Conversation-key guidance invalidation
# =============================================================================

_GUIDANCE_CHANGED_FIELDS_ATTRIBUTE = (
    "_translation_cache_changed_guidance_fields"
)

_GUIDANCE_TRANSLATABLE_FIELDS = (
    "title",
    "content",
)


@receiver(
    pre_save,
    sender=ConversationKeyGuidance,
    dispatch_uid="translations.capture_guidance_translation_changes",
)
def capture_guidance_translation_changes(
    sender,
    instance,
    raw=False,
    **kwargs,
):
    if raw:
        return

    _capture_changed_translation_fields(
        instance=instance,
        model=ConversationKeyGuidance,
        tracked_fields=_GUIDANCE_TRANSLATABLE_FIELDS,
        attribute_name=_GUIDANCE_CHANGED_FIELDS_ATTRIBUTE,
    )


@receiver(
    post_save,
    sender=ConversationKeyGuidance,
    dispatch_uid="translations.invalidate_changed_guidance_fields",
)
def invalidate_changed_guidance_translation_fields(
    sender,
    instance,
    created,
    raw=False,
    **kwargs,
):
    if raw:
        return

    changed_fields = (
        _consume_changed_translation_fields(
            instance=instance,
            attribute_name=(
                _GUIDANCE_CHANGED_FIELDS_ATTRIBUTE
            ),
        )
    )

    if created or not changed_fields:
        return

    _delete_translation_fields_for_instance(
        instance,
        changed_fields,
    )


@receiver(
    post_delete,
    sender=ConversationKeyGuidance,
    dispatch_uid="translations.delete_guidance_cache",
)
def delete_conversation_key_guidance_translations(
    sender,
    instance,
    **kwargs,
):
    _delete_translations_for_instance(
        instance
    )