# apps/accounts/signals/trust_profile_signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models.user import CustomUser
from apps.accounts.services.trust_engine import trigger_trust_recalculation


TRUST_RELATED_FIELDS = {
    "is_active",
    "mobile_number",
    "name",
    "family",
    "birthday",
    "gender",
    "country",
    "primary_language",
    "image_name",
}


@receiver(post_save, sender=CustomUser)
def update_trust_after_profile_change(sender, instance, created, update_fields=None, **kwargs):
    """
    Recalculate trust after relevant profile updates.
    """
    if created:
        trigger_trust_recalculation(instance.id)
        return

    if update_fields is None:
        trigger_trust_recalculation(instance.id)
        return

    if TRUST_RELATED_FIELDS.intersection(set(update_fields)):
        trigger_trust_recalculation(instance.id)