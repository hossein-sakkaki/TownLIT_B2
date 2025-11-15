# apps/notifications/services.py
import logging
from typing import Optional
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from utils.common.push_notification import send_push_notification
from .models import Notification, UserNotificationPreference
from .constants import CHANNEL_PUSH, CHANNEL_WS, CHANNEL_EMAIL
from .tasks import send_email_notification  # Celery async task

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Check if notification type is enabled for user
# -------------------------------------------------------------------------
def _is_enabled(user, notif_type):
    try:
        pref = UserNotificationPreference.objects.get(user=user, notification_type=notif_type)
        return pref.enabled, pref.channels_mask if pref.enabled else 0
    except UserNotificationPreference.DoesNotExist:
        # Default: enabled, all 3 channels active (Push + WS + Email)
        return True, 7


# -------------------------------------------------------------------------
# Safe ContentType resolver
# -------------------------------------------------------------------------
def _safe_ct(obj):
    try:
        return ContentType.objects.get_for_model(obj.__class__) if obj else None
    except Exception as e:
        logger.warning(f"[Notif] Failed to resolve ContentType for {obj}: {e}")
        return None


# -------------------------------------------------------------------------
# URL helpers (prefer action deep-link, then target)
# -------------------------------------------------------------------------
def _safe_get_absolute_url(obj) -> Optional[str]:
    """Return obj.get_absolute_url() or None, never raise."""
    if not obj or not hasattr(obj, "get_absolute_url"):
        return None
    try:
        url = obj.get_absolute_url()
        return url or None
    except Exception as e:
        logger.debug(f"[Notif] get_absolute_url failed for {obj}: {e}")
        return None


def _resolve_link(target_obj, action_obj) -> Optional[str]:
    """Prefer deep-link from the action (comment/reaction), else fallback to target."""
    url = _safe_get_absolute_url(action_obj)
    if url:
        return url
    return _safe_get_absolute_url(target_obj)


# -------------------------------------------------------------------------
# Main entry point
# -------------------------------------------------------------------------
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
    """Centralized notification creation + dispatch (DB + WS + Push + Email)"""

    enabled, channels_mask = _is_enabled(recipient, notif_type)
    if not enabled:
        logger.info(f"[Notif] Skipped (disabled) for user={recipient.id}, type={notif_type}")
        return None

    target_ct = _safe_ct(target_obj)
    target_id = getattr(target_obj, "pk", None)
    action_ct = _safe_ct(action_obj)
    action_id = getattr(action_obj, "pk", None)

    # Prefer provided link; else resolve automatically
    link = link or _resolve_link(target_obj, action_obj)

    dedupe_key = f"{recipient.id}:{actor.id if actor else 0}:{notif_type}:{action_id or 0}:{target_id or 0}"

    def _persist():
        try:
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
            logger.debug(f"[Notif] Created id={notif.id} for user={recipient.id}")
            _deliver_notification(notif, channels_mask)
            return notif
        except Exception as e:
            logger.error(f"[Notif] Failed to persist for user={recipient.id}: {e}", exc_info=True)
            return None

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(lambda: _persist())
    else:
        _persist()


# -------------------------------------------------------------------------
# Deliver across all enabled channels
# -------------------------------------------------------------------------
def _deliver_notification(notif: Notification, channels_mask: int):
    """Fan-out to WebSocket, Push (FCM), and Email via Celery"""

    # --- WebSocket Delivery ---
    try:
        if channels_mask & CHANNEL_WS:
            layer = get_channel_layer()
            if layer:
                async_to_sync(layer.group_send)(
                    f"notif_user_{notif.user_id}",   # ←← FIXED HERE
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
                logger.debug(f"[Notif] WS sent to notif_user_{notif.user_id}")
            else:
                logger.warning(f"[Notif] WS layer unavailable for user {notif.user_id}")
    except Exception as e:
        logger.warning(f"[Notif] WS delivery failed for user {notif.user_id}: {e}", exc_info=True)


    # --- Push Delivery (FCM) ---
    try:
        if channels_mask & CHANNEL_PUSH:
            token = getattr(notif.user, "registration_id", None)
            if token:
                send_push_notification(
                    registration_id=token,
                    message_title="TownLIT Notification",
                    message_body=notif.message,
                )
                logger.debug(f"[Notif] Push sent to user {notif.user_id}")
            else:
                logger.info(f"[Notif] No FCM token for user {notif.user_id}")
    except Exception as e:
        logger.warning(f"[Notif] Push delivery failed for user {notif.user_id}: {e}", exc_info=True)

    # --- Email Delivery (async Celery) ---
    try:
        if channels_mask & CHANNEL_EMAIL:
            email = getattr(notif.user, "email", None)
            if email:
                subject = "New Notification from TownLIT"
                send_email_notification.delay(email, subject, notif.message, notif.link)
                logger.debug(f"[Notif] Email queued to {email}")
            else:
                logger.info(f"[Notif] No email found for user {notif.user_id}")
    except Exception as e:
        logger.warning(f"[Notif] Email delivery failed for user {notif.user_id}: {e}", exc_info=True)
