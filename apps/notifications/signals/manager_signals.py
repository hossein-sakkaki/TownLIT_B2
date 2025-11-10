from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.urls import reverse
from apps.notifications.models import Notification
from utils.common.push_notification import send_push_notification

from apps.profilesOrg.models import OrganizationManager

# Standard Notification for adding a new manager
@receiver(post_save, sender=OrganizationManager)
def notify_organization_members(sender, instance, created, **kwargs):
    if created:
        organization = instance.organization
        manager = instance.member
        notification_type = 'manager_appointed'
        message = f"{manager.name} has been appointed as the new manager of {organization.org_name}."

        for member in organization.members.all():
            Notification.objects.create(
                user=member,
                message=message,
                notification_type=notification_type,
                content_type=ContentType.objects.get_for_model(organization),
                object_id=organization.id,
                link=reverse('Organization_detail', kwargs={'pk': organization.id})
            )

# Push Notification for adding a new manager
@receiver(post_save, sender=OrganizationManager)
def send_manager_push_notification(sender, instance, created, **kwargs):
    if created:
        organization = instance.organization
        manager = instance.member
        message = f"{manager.name} has been appointed as the new manager of {organization.org_name}."

        for member in organization.members.all():
            if member.registration_id:
                send_push_notification(
                    registration_id=member.registration_id,
                    message_title="New Manager Appointed",
                    message_body=message
                )

# Real-time Notification for adding a new manager
@receiver(post_save, sender=OrganizationManager)
def send_manager_real_time_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        organization = instance.organization
        manager = instance.member
        message = f"{manager.name} has been appointed as the new manager of {organization.org_name}."

        for member in organization.members.all():
            async_to_sync(channel_layer.group_send)(
                f"user_{member.id}",
                {
                    "type": "send_notification",
                    "message": message,
                }
            )
