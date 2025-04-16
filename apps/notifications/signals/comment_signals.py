from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.notifications.models import Notification
from apps.posts.models import Comment
from utils import send_push_notification

# Standard Notification for new comment
@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    if created and instance.recomment is None:
        post_author = instance.post.user
        Notification.objects.create(
            user=post_author,
            message=f"{instance.name.username} commented on your post.",
            notification_type='new_comment',
            content_type=ContentType.objects.get_for_model(sender),
            object_id=instance.id,
            link=reverse('Comment_detail', kwargs={'pk': instance.pk})
        )

# Standard Notification for new recomment
@receiver(post_save, sender=Comment)
def create_recomment_notification(sender, instance, created, **kwargs):
    if created and instance.recomment is not None:
        original_comment_author = instance.recomment.name
        post_author = instance.recomment.post.user
        if original_comment_author != instance.name:
            Notification.objects.create(
                user=original_comment_author,
                message=f"{instance.name.username} replied to your comment.",
                notification_type='new_recomment',
                content_type=ContentType.objects.get_for_model(sender),
                object_id=instance.id,
                link=reverse('Comment_detail', kwargs={'pk': instance.pk})
            )

        if post_author != instance.name and post_author != original_comment_author:
            Notification.objects.create(
                user=post_author,
                message=f"{instance.name.username} replied to a comment on your post.",
                notification_type='new_recomment',
                content_type=ContentType.objects.get_for_model(sender),
                object_id=instance.id,
                link=reverse('Comment_detail', kwargs={'pk': instance.pk})
            )

# Push Notification for new comment or recomment
@receiver(post_save, sender=Comment)
def send_comment_push_notification(sender, instance, created, **kwargs):
    if created:
        users_to_notify = []
        if instance.recomment is None:
            users_to_notify.append(instance.post.user)
        else:
            original_comment_author = instance.recomment.name
            post_author = instance.recomment.post.user
            if original_comment_author != instance.name:
                users_to_notify.append(original_comment_author)
            if post_author != instance.name and post_author != original_comment_author:
                users_to_notify.append(post_author)
        
        for user in users_to_notify:
            if user.registration_id:
                message = f"{instance.name.username} commented on your post." if instance.recomment is None else f"{instance.name.username} replied to your comment."
                send_push_notification(
                    registration_id=user.registration_id,
                    message_title="New Comment",
                    message_body=message
                )

# Real-time Notification for new comment or recomment
@receiver(post_save, sender=Comment)
def send_comment_real_time_notification(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        users_to_notify = []
        if instance.recomment is None:
            users_to_notify.append(instance.post.user)
        else:
            original_comment_author = instance.recomment.name
            post_author = instance.recomment.post.user
            if original_comment_author != instance.name:
                users_to_notify.append(original_comment_author)
            if post_author != instance.name and post_author != original_comment_author:
                users_to_notify.append(post_author)

        for user in users_to_notify:
            async_to_sync(channel_layer.group_send)(
                f"user_{user.id}",
                {
                    "type": "send_notification",
                    "message": f"{instance.name.username} commented on your post." if instance.recomment is None else f"{instance.name.username} replied to your comment.",
                }
            )
