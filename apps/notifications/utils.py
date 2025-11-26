# apps/notifications/utils.py

from apps.notifications.models import Notification, UserNotificationPreference
from apps.notifications.constants import CHANNEL_PUSH
from utils.common.push_notification import push_engine


def send_push_for_notification(notification: Notification) -> None:
    """
    Sends push notification IF user has push enabled for this notification type.
    """

    pref = UserNotificationPreference.objects.filter(
        user=notification.recipient,
        notification_type=notification.type
    ).first()

    if not pref:
        return   

    # User has disabled push for this type
    if not (pref.channels_mask & CHANNEL_PUSH):
        return

    title = notification.title or "TownLIT Notification"
    body = notification.body or notification.message or ""

    data = {
        "notification_id": notification.id,
        "type": notification.type,
        "link": notification.link,
    }

    # Use global engine
    push_engine.send_to_user(
        user=notification.recipient,
        title=title,
        body=body,
        data=data
    )
