# apps/notifications/services.py

import logging
from typing import Optional
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from typing import Optional, Dict, Any

from utils.firebase.push_engine import push_engine  # NEW: Firebase REST engine
from .models import Notification, UserNotificationPreference
from .constants import (
    CHANNEL_PUSH,
    CHANNEL_WS,
    CHANNEL_EMAIL,
    CHANNEL_DEFAULT,
    NOTIFICATION_TYPES_PUSH_EMAIL_ONLY,
)

from .tasks import send_email_notification  # Celery async task

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Check if notification type is enabled for user
# -------------------------------------------------------------------------
def _is_enabled(user, notif_type):
    try:
        pref = UserNotificationPreference.objects.get(
            user=user,
            notification_type=notif_type,
        )
        return pref.enabled, (pref.channels_mask if pref.enabled else 0)
    except UserNotificationPreference.DoesNotExist:
        # Default: enabled, all 3 channels active (Push + WS + Email)
        return True, CHANNEL_DEFAULT


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


# -------------------------------------------------------------------------
# Deep-link helpers
# -------------------------------------------------------------------------
def _resolve_link(target_obj, action_obj) -> Optional[str]:
    """
    Prefer deep-link from the action (comment/reaction),
    else fallback to target object.
    """
    url = _safe_get_absolute_url(action_obj)
    if url:
        return url
    return _safe_get_absolute_url(target_obj)


# -------------------------------------------------------------------------
# FCM data helpers
# -------------------------------------------------------------------------
def _stringify_data(data: Dict[str, Any]) -> Dict[str, str]:
    """FCM requires all data values to be strings."""
    safe = {}
    for k, v in data.items():
        if v is None:
            safe[k] = ""
        else:
            safe[k] = str(v)
    return safe

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
    extra_payload: Optional[Dict[str, Any]] = None,
):
    """
    Centralized notification creation + dispatch
    (DB + WebSocket + Push + Email).
    """

    logger.error(
        "🔥 SERVICE START → notif_type=%s | recipient=%s | actor=%s",
        notif_type,
        recipient.id,
        actor.id if actor else None,
    )

    # Resolve user preference + channel mask
    enabled, channels_mask = _is_enabled(recipient, notif_type)

    logger.error(
        "🔥 CHECK ENABLE → user=%s | enabled=%s | channels_mask=%s",
        recipient.id,
        enabled,
        channels_mask,
    )

    # For some types (e.g. messages) we only want Push + Email, no WS
    if notif_type in NOTIFICATION_TYPES_PUSH_EMAIL_ONLY:
        # Keep only PUSH + EMAIL bits, drop WebSocket
        channels_mask = channels_mask & (CHANNEL_PUSH | CHANNEL_EMAIL)

    if not enabled:
        logger.error(
            "⛔ SERVICE STOP: Notification disabled → user=%s type=%s",
            recipient.id,
            notif_type,
        )
        return None

    target_ct = _safe_ct(target_obj)
    target_id = getattr(target_obj, "pk", None)
    action_ct = _safe_ct(action_obj)
    action_id = getattr(action_obj, "pk", None)

    # Prefer explicit link, else deep-link resolver
    link = link or _resolve_link(target_obj, action_obj)

    dedupe_key = (
        f"{recipient.id}:{actor.id if actor else 0}:"
        f"{notif_type}:{action_id or 0}:{target_id or 0}"
    )

    logger.error(
        "🔥 BUILD NOTIF → target_id=%s | action_id=%s | link=%s | dedupe_key=%s",
        target_id,
        action_id,
        link,
        dedupe_key,
    )

    def _persist():
        logger.error("🔥 DB WRITE START → user=%s", recipient.id)
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

            logger.error(
                "🔥 DB WRITE OK → notif_id=%s | user=%s",
                notif.id,
                recipient.id,
            )

            # Fan-out to WS / Push / Email according to channels_mask
            _deliver_notification(notif, channels_mask, extra_payload)

            return notif

        except Exception as e:
            logger.error(
                "⛔ DB WRITE FAILED → user=%s | error=%s",
                recipient.id,
                e,
                exc_info=True,
            )
            return None

    if transaction.get_connection().in_atomic_block:
        logger.error("⚠️ In atomic block → using on_commit")
        transaction.on_commit(lambda: _persist())
    else:
        _persist()




# -------------------------------------------------------------------------
# Deliver across all enabled channels
# -------------------------------------------------------------------------
def _deliver_notification(
    notif: Notification,
    channels_mask: int,
    extra_payload: Optional[Dict[str, Any]] = None,
):
    """
    Fan-out to WebSocket, Push (Firebase REST), and Email via Celery.
    """

    # ------------------------------------------------------------------
    # 1) WebSocket Delivery
    # ------------------------------------------------------------------
    try:
        if channels_mask & CHANNEL_WS:
            layer = get_channel_layer()
            if layer:
                payload = {
                    "id": notif.id,
                    "type": notif.notification_type,
                    "message": notif.message,
                    "link": notif.link,
                    "created_at": notif.created_at.isoformat(),
                    "is_read": notif.is_read,
                }

                if extra_payload:
                    payload["extra"] = extra_payload

                async_to_sync(layer.group_send)(
                    f"notif_user_{notif.user_id}",
                    {
                        "type": "send_notification",
                        "payload": payload,
                    },
                )

                logger.debug(
                    "[Notif] WS sent to group notif_user_%s",
                    notif.user_id,
                )
    except Exception as e:
        logger.warning(
            "[Notif] WS delivery failed for user %s: %s",
            notif.user_id,
            e,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # 2) Push Delivery (Firebase REST)
    # ------------------------------------------------------------------
    try:
        if channels_mask & CHANNEL_PUSH:

            base_data = {
                "link": notif.link or "",
                "notification_type": notif.notification_type,
                "notification_id": str(notif.id),
            }

            # Add extra payload
            if extra_payload:
                try:
                    base_data.update(extra_payload)
                except Exception as e:
                    logger.warning(
                        "[Notif] extra_payload merge failed for notif %s: %s",
                        notif.id,
                        e,
                        exc_info=True,
                    )

            # 🔥 FCM requires all values to be strings
            safe_data = {}
            for key, value in base_data.items():
                safe_data[key] = "" if value is None else str(value)

            logger.debug("🔥 PUSH DATA READY → %s", safe_data)

            push_engine.send_to_user(
                notif.user,
                title="TownLIT Notification",
                body=notif.message,
                data=safe_data,
            )

            logger.debug(
                "[Notif] Push dispatched via Firebase REST for user %s",
                notif.user_id,
            )

    except Exception as e:
        logger.warning(
            "[Notif] Push delivery failed for user %s: %s",
            notif.user_id,
            e,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # 3) Email Delivery
    # ------------------------------------------------------------------
    try:
        if channels_mask & CHANNEL_EMAIL:
            email = getattr(notif.user, "email", None)

            if email:
                subject = "New Notification from TownLIT"

                email_extra = ""
                if extra_payload:
                    for k, v in extra_payload.items():
                        email_extra += f"\n{k}: {v}"

                body_text = (
                    f"{notif.message}"
                )

                send_email_notification.delay(
                    email,
                    subject,
                    body_text,
                    notif.link,
                )

                logger.debug(
                    "[Notif] Email queued to %s",
                    email,
                )

            else:
                logger.info(
                    "[Notif] No email found for user %s",
                    notif.user_id,
                )

    except Exception as e:
        logger.warning(
            "[Notif] Email delivery failed for user %s: %s",
            notif.user_id,
            e,
            exc_info=True,
        )
