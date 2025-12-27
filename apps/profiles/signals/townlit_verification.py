# apps/profiles/signals/townlit_verification.py

from django.db.models.signals import post_save, m2m_changed, post_delete
from django.dispatch import receiver

from apps.profiles.models import Member
from apps.profiles.services.townlit_verification.applier import apply_townlit_verification
from django.contrib.contenttypes.models import ContentType
from apps.posts.models.testimony import Testimony  # adjust import path to your Testimony model
from apps.profiles.models import MemberSpiritualGifts


@receiver(post_save, sender=Member)
def on_member_saved(sender, instance: Member, created: bool, **kwargs):
    # Re-evaluate after member save
    apply_townlit_verification(instance, source="member_save")


@receiver(m2m_changed, sender=Member.service_types.through)
def on_member_service_types_changed(sender, instance: Member, action: str, **kwargs):
    # Re-evaluate when service types change
    if action in ("post_add", "post_remove", "post_clear"):
        apply_townlit_verification(instance, source="service_types_changed")


@receiver(post_save, sender=Testimony)
def on_testimony_saved(sender, instance: Testimony, created: bool, **kwargs):
    # Re-evaluate when testimony created/updated
    if not instance.content_type_id or not instance.object_id:
        return
    member_ct = ContentType.objects.get_for_model(Member)
    if instance.content_type_id != member_ct.id:
        return
    try:
        member = Member.objects.get(pk=instance.object_id)
    except Member.DoesNotExist:
        return
    apply_townlit_verification(member, source="testimony_saved")


@receiver(post_delete, sender=Testimony)
def on_testimony_deleted(sender, instance: Testimony, **kwargs):
    # Re-evaluate when testimony deleted
    if not instance.content_type_id or not instance.object_id:
        return
    member_ct = ContentType.objects.get_for_model(Member)
    if instance.content_type_id != member_ct.id:
        return
    try:
        member = Member.objects.get(pk=instance.object_id)
    except Member.DoesNotExist:
        return
    apply_townlit_verification(member, source="testimony_deleted")


@receiver(post_save, sender=MemberSpiritualGifts)
def on_spiritual_gifts_saved(sender, instance: MemberSpiritualGifts, created: bool, **kwargs):
    # Re-evaluate when spiritual gifts saved
    apply_townlit_verification(instance.member, source="spiritual_gifts_saved")


@receiver(m2m_changed, sender=MemberSpiritualGifts.gifts.through)
def on_spiritual_gifts_changed(sender, instance: MemberSpiritualGifts, action: str, **kwargs):
    # Re-evaluate when gifts m2m changes
    if action in ("post_add", "post_remove", "post_clear"):
        apply_townlit_verification(instance.member, source="spiritual_gifts_changed")
