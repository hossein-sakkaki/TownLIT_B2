# apps/translations/services/base.py

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings

from apps.translations.models import TranslationCache
from apps.translations.selectors import get_cached_translation
from apps.translations.services.aws_translate import AWSTranslateClient
from apps.translations.services.hashing import hash_text
from apps.translations.services.language import resolve_target_language
from apps.translations.services.exceptions import EmptySourceTextError
from apps.translations.services.llm_humanize import humanize_translation


def _humanize_enabled() -> bool:
    """Check if LLM humanization is globally enabled."""
    return bool(getattr(settings, "TRANSLATIONS_HUMANIZE_ENABLED", False))


def _current_prompt_version() -> str:
    """Return current humanization prompt version."""
    return getattr(settings, "TRANSLATIONS_HUMANIZE_PROMPT_VERSION", "")


def translate_cached(
    *,
    obj,
    field_name: str,
    user=None,
    target_language: str | None = None,
    source_language: str | None = None,
) -> dict:
    """
    Translate a text field with cache support.
    Applies LLM humanization once per prompt version
    and stores final result.
    """

    # -------------------------------------------------
    # 0) Source text validation
    # -------------------------------------------------
    source_text = getattr(obj, field_name, None)
    if not source_text or not source_text.strip():
        raise EmptySourceTextError("Source text is empty.")

    source_text_hash = hash_text(source_text)
    content_type = ContentType.objects.get_for_model(obj)

    resolved_target_language = resolve_target_language(
        user=user,
        source_language=source_language,
        override_language=target_language,
    )

    current_prompt_version = _current_prompt_version()

    # -------------------------------------------------
    # 1) Try cache
    # -------------------------------------------------
    cached = get_cached_translation(
        content_type=content_type,
        object_id=obj.pk,
        field_name=field_name,
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
    )

    if cached:
        cached.touch()

        needs_upgrade = (
            _humanize_enabled()
            and (
                not cached.is_humanized
                or cached.prompt_version != current_prompt_version
            )
        )

        if needs_upgrade:
            try:
                h = humanize_translation(
                    source_text=source_text,
                    translated_text=cached.translated_text,
                    target_language=resolved_target_language,
                )
                cached.translated_text = h["text"]
                cached.engine = "aws+llm"
                cached.is_humanized = True
                cached.llm_model = h["model"]
                cached.prompt_version = h["prompt_version"]
                cached.humanized_at = timezone.now()
                cached.save(
                    update_fields=[
                        "translated_text",
                        "engine",
                        "is_humanized",
                        "llm_model",
                        "prompt_version",
                        "humanized_at",
                    ]
                )
            except Exception:
                # Fail-safe: keep existing cached text
                pass

        return {
            "text": cached.translated_text,
            "source_language": cached.source_language,
            "target_language": cached.target_language,
            "cached": True,
        }

    # -------------------------------------------------
    # 2) AWS base translation
    # -------------------------------------------------
    aws_client = AWSTranslateClient()
    aws_result = aws_client.translate(
        text=source_text,
        target_language=resolved_target_language,
        source_language=source_language,
    )

    final_text = aws_result["translated_text"]
    engine = "aws"
    is_humanized = False
    llm_model = ""
    prompt_version = ""
    humanized_at = None

    # -------------------------------------------------
    # 3) LLM humanization (one-time per version)
    # -------------------------------------------------
    if _humanize_enabled():
        try:
            h = humanize_translation(
                source_text=source_text,
                translated_text=final_text,
                target_language=resolved_target_language,
            )
            final_text = h["text"]
            engine = "aws+llm"
            is_humanized = True
            llm_model = h["model"]
            prompt_version = h["prompt_version"]
            humanized_at = timezone.now()
        except Exception:
            # Fail-safe: keep AWS output
            pass

    # -------------------------------------------------
    # 4) Store cache
    # -------------------------------------------------
    TranslationCache.objects.create(
        content_type=content_type,
        object_id=obj.pk,
        field_name=field_name,
        source_language=aws_result["source_language"],
        target_language=resolved_target_language,
        source_text_hash=source_text_hash,
        translated_text=final_text,
        last_accessed_at=timezone.now(),
        engine=engine,
        is_humanized=is_humanized,
        llm_model=llm_model,
        prompt_version=prompt_version,
        humanized_at=humanized_at,
    )

    return {
        "text": final_text,
        "source_language": aws_result["source_language"],
        "target_language": resolved_target_language,
        "cached": False,
    }
