# signals.py
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from apps.profiles.models import MemberServiceType

@receiver(pre_save, sender=MemberServiceType)
def delete_old_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    if old.document and old.document != instance.document:
        old.document.delete(save=False)

@receiver(post_delete, sender=MemberServiceType)
def delete_file_on_delete(sender, instance, **kwargs):
    if instance.document:
        instance.document.delete(save=False)
