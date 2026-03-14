# apps/sanctuary/signals/townlit_report_signals.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profiles.models import Member
from apps.sanctuary.models import SanctuaryRequest
from apps.accounts.services.townlit_trigger import trigger_member_townlit_evaluation

User = get_user_model()


@receiver(post_save, sender=SanctuaryRequest)
def townlit_after_sanctuary_request(sender, instance, created, **kwargs):
    if not created:
        return

    user_ct = ContentType.objects.get_for_model(User)
    if instance.content_type_id != user_ct.id:
        return

    member = Member.objects.filter(user_id=instance.object_id).only("id").first()
    if member:
        trigger_member_townlit_evaluation(member.id)