# apps/notifications/services.py
from typing import Optional
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.core.mail import send_mail

from utils.common.push_notification import send_push_notification
from .models import Notification, UserNotificationPreference
from .constants import CHANNEL_PUSH, CHANNEL_WS, CHANNEL_EMAIL
from .tasks import send_email_notification  # Celery task

# --- Pref check -----------------------------------------------------------
def _is_enabled(user, notif_type):
    try:
        pref = UserNotificationPreference.objects.get(user=user, notification_type=notif_type)
        return pref.enabled, pref.channels_mask
    except UserNotificationPreference.DoesNotExist:
        return True, 7  # All three enabled by default

# --- Safe CT --------------------------------------------------------------
def _safe_ct(obj):
    return ContentType.objects.get_for_model(obj.__class__) if obj else None

# --- Main function --------------------------------------------------------
def create_and_dispatch_notification(
    *,
    recipient,
    actor=None,
    notif_type: str,
    message: str,
    target_obj=None,
    action_obj=None,
    link: Optional[str] = None,
    dedupe: bool = True,
):
    """Centralized notification creation and dispatch"""
    enabled, channels_mask = _is_enabled(recipient, notif_type)
    if not enabled:
        return None

    target_ct = _safe_ct(target_obj)
    target_id = getattr(target_obj, "pk", None)
    action_ct = _safe_ct(action_obj)
    action_id = getattr(action_obj, "pk", None)
    dedupe_key = f"{recipient.id}:{actor.id if actor else 0}:{notif_type}:{action_id or 0}:{target_id or 0}"

    def _persist():
        notif = Notification.objects.create(
            user=recipient,
            actor=actor,
            message=message,
            notification_type=notif_type,
            target_content_type=target_ct,
            target_object_id=target_id,
            action_content_type=action_ct,
            action_object_id=action_id,
            link=link,
            dedupe_key=dedupe_key,
        )
        _deliver_notification(notif, channels_mask)
        return notif

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(lambda: _persist())
    else:
        _persist()

# --- Delivery -------------------------------------------------------------
def _deliver_notification(notif: Notification, channels_mask: int):
    """Fan-out to Push, WS, and Email channels"""
    # --- WebSocket ---
    try:
        if channels_mask & CHANNEL_WS:
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f"user_{notif.user_id}",
                    {
                        "type": "send_notification",
                        "payload": {
                            "id": notif.id,
                            "type": notif.notification_type,
                            "message": notif.message,
                            "link": notif.link,
                            "created_at": notif.created_at.isoformat(),
                            "is_read": notif.is_read,
                        },
                    },
                )
    except Exception:
        pass

    # --- Push (FCM) ---
    try:
        if channels_mask & CHANNEL_PUSH:
            token = getattr(notif.user, "registration_id", None)
            if token:
                send_push_notification(
                    registration_id=token,
                    message_title="TownLIT Notification",
                    message_body=notif.message,
                )
    except Exception:
        pass

    # --- Email (Celery async) ---
    try:
        if channels_mask & CHANNEL_EMAIL:
            email = getattr(notif.user, "email", None)
            if email:
                subject = "New Notification from TownLIT"
                send_email_notification.delay(email, subject, notif.message, notif.link)
    except Exception:
        pass
