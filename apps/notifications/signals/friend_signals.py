from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.notifications.models import Notification
from apps.profiles.models import Friendship
from utils import send_push_notification

# Standard Notification for Friend Request
@receiver(post_save, sender=Friendship)
def create_friend_request_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        Notification.objects.create(
            user=instance.to_user,
            message=f"{instance.from_user.username} sent you a friend request.",
            notification_type='friend_request_received',
            content_type=ContentType.objects.get_for_model(sender),
            object_id=instance.id,
            link=instance.get_absolute_url()
        )

# Standard Notification for Accepted Friend Request
@receiver(post_save, sender=Friendship)
def accept_friend_request_notification(sender, instance, **kwargs):
    if instance.status == 'accepted':
        Notification.objects.create(
            user=instance.from_user,
            message=f"{instance.to_user.username} accepted your friend request.",
            notification_type='friend_request_accepted',
            content_type=ContentType.objects.get_for_model(sender),
            object_id=instance.id,
            link=instance.get_absolute_url()
        )

# Standard Notification for Declined Friend Request
@receiver(post_save, sender=Friendship)
def decline_friend_request_notification(sender, instance, **kwargs):
    if instance.status == 'declined':
        Notification.objects.create(
            user=instance.from_user,
            message=f"{instance.to_user.username} declined your friend request.",
            notification_type='friend_request_declined',
            content_type=ContentType.objects.get_for_model(sender),
            object_id=instance.id,
            link=instance.get_absolute_url()
        )

# Push Notification for Friend Request
@receiver(post_save, sender=Friendship)
def send_friend_request_push_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        if instance.to_user.registration_id:
            send_push_notification(
                registration_id=instance.to_user.registration_id,
                message_title="Friend Request",
                message_body=f"{instance.from_user.username} sent you a friend request."
            )

# Push Notification for Accepted Friend Request
@receiver(post_save, sender=Friendship)
def send_accept_friend_request_push_notification(sender, instance, **kwargs):
    if instance.status == 'accepted':
        if instance.from_user.registration_id:
            send_push_notification(
                registration_id=instance.from_user.registration_id,
                message_title="Friend Request Accepted",
                message_body=f"{instance.to_user.username} accepted your friend request."
            )

# Push Notification for Declined Friend Request
@receiver(post_save, sender=Friendship)
def send_decline_friend_request_push_notification(sender, instance, **kwargs):
    if instance.status == 'declined':
        if instance.from_user.registration_id:
            send_push_notification(
                registration_id=instance.from_user.registration_id,
                message_title="Friend Request Declined",
                message_body=f"{instance.to_user.username} declined your friend request."
            )

# Real-time Notification for Friend Request
@receiver(post_save, sender=Friendship)
def send_friend_request_real_time_notification(sender, instance, created, **kwargs):
    if created and instance.status == 'pending':
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.to_user.id}",
            {
                "type": "send_notification",
                "message": f"{instance.from_user.username} sent you a friend request.",
            }
        )

# Real-time Notification for Accepted Friend Request
@receiver(post_save, sender=Friendship)
def send_accept_friend_request_real_time_notification(sender, instance, **kwargs):
    if instance.status == 'accepted':
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.from_user.id}",
            {
                "type": "send_notification",
                "message": f"{instance.to_user.username} accepted your friend request.",
            }
        )

# Real-time Notification for Declined Friend Request
@receiver(post_save, sender=Friendship)
def send_decline_friend_request_real_time_notification(sender, instance, **kwargs):
    if instance.status == 'declined':
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{instance.from_user.id}",
            {
                "type": "send_notification",
                "message": f"{instance.to_user.username} declined your friend request.",
            }
        )
