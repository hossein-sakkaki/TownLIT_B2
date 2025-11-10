# apps/notifications/signals/post_signals.py
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse, NoReverseMatch
from django.contrib.contenttypes.models import ContentType

from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.notifications.models import Notification
from apps.posts.models import (
    Moment, Testimony, Pray, Announcement, Lesson, Preach, Worship, Witness, Library
)
from utils.common.push_notification import send_push_notification



POST_MODELS = (Moment, Testimony, Pray, Announcement, Lesson, Preach, Worship, Witness, Library)

ROUTE_MAP = {
    Moment:       ("posts:moment-detail",        "pk",   lambda i: f"New Moment: {(getattr(i, 'content', '') or '')[:30]}..."),
    Testimony:    ("posts:testimony-detail",     "slug", lambda i: f"New Testimony: {getattr(i, 'title', '') or 'Untitled'}"),
    Pray:         ("posts:prayer-detail",        "pk",   lambda i: f"New Pray: {getattr(i, 'title', '') or 'Untitled'}"),
    Announcement: ("posts:announcement-detail",  "pk",   lambda i: f"New Announcement: {getattr(i, 'title', '') or 'Untitled'}"),
    Lesson:       ("posts:lesson-detail",        "pk",   lambda i: f"New Lesson: {getattr(i, 'title', '') or 'Untitled'}"),
    Preach:       ("posts:preach-detail",        "pk",   lambda i: f"New Preach: {getattr(i, 'title', '') or 'Untitled'}"),
    Worship:      ("posts:worship-detail",       "pk",   lambda i: f"New Worship: {getattr(i, 'title', '') or 'Untitled'}"),
    Witness:      ("posts:witness-detail",       "pk",   lambda i: f"New Witness: {getattr(i, 'title', '') or 'Untitled'}"),
    Library:      ("posts:library-detail",       "pk",   lambda i: f"New Library Item: {getattr(i, 'book_name', '') or 'Untitled'}"),
}

TYPE_NAME_MAP = {
    Moment:       "new_moment",
    Testimony:    "new_testimony",
    Pray:         "new_pray",
    Announcement: "new_announcement",
    Lesson:       "new_lesson",
    Preach:       "new_preach",
    Worship:      "new_worship",
    Witness:      "new_witness",
    Library:      "new_library_item",
}

def _safe_reverse(route_name: str, kw_name: str, instance) -> str | None:
    value = getattr(instance, kw_name, None)
    if value is None and kw_name == "slug" and getattr(instance, "pk", None):
        kw_name, value = "pk", instance.pk
    try:
        if value is not None:
            return reverse(route_name, kwargs={kw_name: value})
    except NoReverseMatch:
        if getattr(instance, "pk", None) and kw_name != "pk":
            try:
                return reverse(route_name, kwargs={"pk": instance.pk})
            except Exception:
                return None
    except Exception:
        return None
    return None

@receiver(post_save, sender=Moment)
@receiver(post_save, sender=Testimony)
@receiver(post_save, sender=Pray)
@receiver(post_save, sender=Announcement)
@receiver(post_save, sender=Lesson)
@receiver(post_save, sender=Preach)
@receiver(post_save, sender=Worship)
@receiver(post_save, sender=Witness)
@receiver(post_save, sender=Library)
def handle_post_created(sender, instance, created, **kwargs):
    """
    Defer side-effects until AFTER COMMIT to avoid touching objects/links
    before they're durably persisted. Still best-effort & non-fatal.
    """
    if not created:
        return

    def _after_commit():
        notif_type = TYPE_NAME_MAP.get(type(instance))
        route_info = ROUTE_MAP.get(type(instance))
        if not notif_type or not route_info:
            return

        route_name, kw_name, msg_builder = route_info
        message = msg_builder(instance) if callable(msg_builder) else "New content"
        link = _safe_reverse(route_name, kw_name, instance)

        # NOTE: اگر برخی مدل‌ها user مستقیم ندارند، اینجا اگر لازم شد از owner دیگر استخراج کن
        user = getattr(instance, "user", None)

        # 1) DB Notification (best-effort)
        try:
            Notification.objects.create(
                user=user,
                message=message,
                notification_type=notif_type,
                content_type=ContentType.objects.get_for_model(type(instance)),
                object_id=instance.pk,
                link=link,
            )
        except Exception:
            pass

        # 2) Push notification (best-effort)
        try:
            reg_id = getattr(user, "registration_id", None) if user else None
            if reg_id:
                send_push_notification(
                    registration_id=reg_id,
                    message_title="New Content",
                    message_body=message,
                )
        except Exception:
            pass

        # 3) Realtime via Channels (best-effort)
        try:
            if user and getattr(user, "id", None):
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {"type": "send_notification", "message": message, "link": link, "kind": notif_type},
                )
        except Exception:
            pass

    transaction.on_commit(_after_commit)  # ← کل منطق بعد از COMMIT




# from django.db.models.signals import post_save
# from django.dispatch import receiver
# from django.urls import reverse
# from django.contrib.contenttypes.models import ContentType
# from channels.layers import get_channel_layer
# from asgiref.sync import async_to_sync
# from apps.notifications.models import Notification
# from apps.posts.models import Moment, Testimony, Pray, Announcement, Lesson, Preach, Worship, Witness, Library
# from utils.common.utils import send_push_notification

# # Standard Notification for new post-related content
# @receiver(post_save, sender=Moment)
# @receiver(post_save, sender=Testimony)
# @receiver(post_save, sender=Pray)
# @receiver(post_save, sender=Announcement)
# @receiver(post_save, sender=Lesson)
# @receiver(post_save, sender=Preach)
# @receiver(post_save, sender=Worship)
# @receiver(post_save, sender=Witness)
# @receiver(post_save, sender=Library)

# def create_post_notification(sender, instance, created, **kwargs):
#     if created:
#         notification_type = None
#         message = None
#         link = None

#         if isinstance(instance, Moment):
#             notification_type = 'new_moment'
#             message = f"New Moment Created: {instance.content[:30]}..."
#             link = reverse('Moment_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Testimony):
#             notification_type = 'new_testimony'
#             message = f"New Testimony: {instance.title}"
#             link = reverse('Testimony_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Pray):
#             notification_type = 'new_pray'
#             message = f"New Pray: {instance.title}"
#             link = reverse('Pray_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Announcement):
#             notification_type = 'new_announcement'
#             message = f"New Announcement: {instance.title}"
#             link = reverse('Announcement_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Lesson):
#             notification_type = 'new_lesson'
#             message = f"New Lesson: {instance.title}"
#             link = reverse('Lesson_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Preach):
#             notification_type = 'new_preach'
#             message = f"New Preach: {instance.title}"
#             link = reverse('Preach_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Worship):
#             notification_type = 'new_worship'
#             message = f"New Worship: {instance.title}"
#             link = reverse('Worship_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Witness):
#             notification_type = 'new_witness'
#             message = f"New Witness: {instance.title}"
#             link = reverse('Witness_detail', kwargs={'pk': instance.pk})
#         elif isinstance(instance, Library):
#             notification_type = 'new_library_item'
#             message = f"New Library Item: {instance.book_name}"
#             link = reverse('Library_detail', kwargs={'pk': instance.pk})

#         if notification_type:
#             Notification.objects.create(
#                 user=instance.user,
#                 message=message,
#                 notification_type=notification_type,
#                 content_type=ContentType.objects.get_for_model(sender),
#                 object_id=instance.id,
#                 link=link
#             )

# # Push Notification for new post-related content
# @receiver(post_save, sender=Moment)
# @receiver(post_save, sender=Testimony)
# @receiver(post_save, sender=Pray)
# @receiver(post_save, sender=Announcement)
# @receiver(post_save, sender=Lesson)
# @receiver(post_save, sender=Preach)
# @receiver(post_save, sender=Worship)
# @receiver(post_save, sender=Witness)
# @receiver(post_save, sender=Library)
# def send_post_push_notification(sender, instance, created, **kwargs):
#     if created:
#         to_user = instance.user
#         if to_user.registration_id:
#             message = f"New Content Added: {instance.title}" if hasattr(instance, 'title') else f"New Post: {instance.content[:30]}..."
#             send_push_notification(
#                 registration_id=to_user.registration_id,
#                 message_title="New Content",
#                 message_body=message
#             )

# # Real-time Notification for new post-related content
# @receiver(post_save, sender=Moment)
# @receiver(post_save, sender=Testimony)
# @receiver(post_save, sender=Pray)
# @receiver(post_save, sender=Announcement)
# @receiver(post_save, sender=Lesson)
# @receiver(post_save, sender=Preach)
# @receiver(post_save, sender=Worship)
# @receiver(post_save, sender=Witness)
# @receiver(post_save, sender=Library)
# def send_post_real_time_notification(sender, instance, created, **kwargs):
#     if created:
#         channel_layer = get_channel_layer()
#         async_to_sync(channel_layer.group_send)(
#             f"user_{instance.user.id}",
#             {
#                 "type": "send_notification",
#                 "message": f"New Content Added: {instance.title}" if hasattr(instance, 'title') else f"New Post: {instance.content[:30]}...",
#             }
#         )
