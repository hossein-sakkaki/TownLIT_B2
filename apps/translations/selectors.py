# apps/translations/selectors.py

from apps.translations.models import TranslationCache


def get_cached_translation(
    *,
    content_type,
    object_id,
    field_name: str,
    target_language: str,
    source_text_hash: str,
):
    """Fetch cached translation if exists."""
    return TranslationCache.objects.filter(
        content_type=content_type,
        object_id=object_id,
        field_name=field_name,
        target_language=target_language,
        source_text_hash=source_text_hash,
    ).first()
