# apps/sanctuary/signals/trust_report_signals.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.sanctuary.models import SanctuaryRequest
from apps.accounts.services.trust_engine import trigger_trust_recalculation

User = get_user_model()


@receiver(post_save, sender=SanctuaryRequest)
def trust_after_sanctuary_request(sender, instance, created, **kwargs):
    """
    Recalculate trust when an account is reported.
    """
    if not created:
        return

    user_ct = ContentType.objects.get_for_model(User)

    if instance.content_type_id != user_ct.id:
        return

    trigger_trust_recalculation(instance.object_id)