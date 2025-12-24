from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.accounts.models import UserDeviceKey
from apps.accounts.services.sender_verification import invalidate_sender_verification_cache


# -----------------------------------------------------------------------
@receiver(post_save, sender=UserDeviceKey)
def _udk_saved(sender, instance: UserDeviceKey, **kwargs):
    # Clear cache whenever the key record changes (verify status, rotation, deactivate, etc.)
    invalidate_sender_verification_cache(instance.user_id, instance.device_id)

@receiver(post_delete, sender=UserDeviceKey)
def _udk_deleted(sender, instance: UserDeviceKey, **kwargs):
    invalidate_sender_verification_cache(instance.user_id, instance.device_id)