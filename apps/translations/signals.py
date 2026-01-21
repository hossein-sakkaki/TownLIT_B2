# apps/translations/signals.py

from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.translations.models import TranslationCache
from apps.posts.models.testimony import Testimony
from apps.posts.models.moment import Moment


def _delete_translations_for_instance(instance):
    """Delete all translations for a given model instance."""
    ct = ContentType.objects.get_for_model(instance.__class__)
    TranslationCache.objects.filter(
        content_type=ct,
        object_id=instance.pk,
    ).delete()


@receiver(post_delete, sender=Testimony)
def delete_testimony_translations(sender, instance, **kwargs):
    _delete_translations_for_instance(instance)


@receiver(post_delete, sender=Moment)
def delete_moment_translations(sender, instance, **kwargs):
    _delete_translations_for_instance(instance)
