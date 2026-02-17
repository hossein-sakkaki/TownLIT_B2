# apps/notifications/services/services.py

import logging
from typing import Optional
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from typing import Optional, Dict, Any

from utils.firebase.push_engine import push_engine  # NEW: Firebase REST engine
from apps.notifications.models import Notification, UserNotificationPreference
from apps.notifications.constants import (
    CHANNEL_PUSH,
    CHANNEL_WS,
    CHANNEL_EMAIL,
    CHANNEL_DEFAULT,
    NOTIFICATION_TYPES_PUSH_EMAIL_ONLY,
)
from apps.notifications.services.ui_link_resolver import (
    build_content_link,
    guess_entry_section, 
    ENTRY_BY_CT
) 

from apps.notifications.tasks import send_email_notification  # Celery async task

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
# Smart UI deep-link resolver (comment/reply aware)
# -------------------------------------------------------------------------
def _ct_key_for_obj(obj) -> str | None:
    """Return 'app_label.model' for obj, or None."""
    if not obj:
        return None
    try:
        m = getattr(obj, "_meta", None)
        if not m:
            return None
        return f"{m.app_label}.{m.model_name}"
    except Exception:
        return None


def _safe_get_slug(obj) -> str | None:
    """Prefer slug; fallback to pk as string."""
    if not obj:
        return None
    s = getattr(obj, "slug", None)
    if s:
        return str(s)
    pk = getattr(obj, "pk", None)
    return str(pk) if pk is not None else None


def _resolve_root_content_from_action(action_obj):
    """
    If action has content_type/object_id (like Comment), resolve root content object.
    No model imports.
    """
    try:
        ct = getattr(action_obj, "content_type", None)
        oid = getattr(action_obj, "object_id", None)
        if ct and oid:
            return ct.get_object_for_this_type(pk=oid)
    except Exception:
        return None
    return None


def _guess_mode_for_obj(obj) -> str:
    """
    Guess universal viewer type.
    - voice: audio/voice types
    - media: video/image fields
    - read: default
    """
    if not obj:
        return "read"

    t = getattr(obj, "type", None)
    if isinstance(t, str) and t.lower() in ("audio", "voice"):
        return "voice"

    # media heuristics
    if getattr(obj, "video", None) or getattr(obj, "video_key", None) or getattr(obj, "video_signed_url", None):
        return "media"
    if getattr(obj, "image", None) or getattr(obj, "image_key", None) or getattr(obj, "image_signed_url", None):
        return "media"
    if getattr(obj, "thumbnail", None) or getattr(obj, "thumbnail_key", None) or getattr(obj, "thumbnail_signed_url", None):
        return "media"

    return "read"


def _smart_ui_link(target_obj, action_obj, extra_payload: dict | None) -> str | None:
    """
    Build /content deep-link ONLY for registered content types in ENTRY_BY_CT.
    For non-content models (Friendship/Fellowship), return None to allow fallback.
    """

    # 0) Resolve root (for comment/reply/reaction)
    root = _resolve_root_content_from_action(action_obj) or target_obj
    if not root:
        return None

    # 1) Only content types we explicitly support
    ct_key = _ct_key_for_obj(root) or ""
    if ct_key not in ENTRY_BY_CT:
        return None  # ✅ prevents /content/<pk> for Friendship/Fellowship

    # 2) Focus (reply > comment > reaction)
    comment_id = parent_id = reaction_id = None
    if isinstance(extra_payload, dict):
        comment_id = extra_payload.get("comment_id")
        parent_id = extra_payload.get("parent_id")
        reaction_id = extra_payload.get("reaction_id")

    focus = None
    if comment_id:
        focus = f"reply-{comment_id}:parent-{parent_id}" if parent_id else f"comment-{comment_id}"
    elif reaction_id:
        focus = f"reaction-{reaction_id}"

    # 3) Slug (content objects should have slug)
    slug = getattr(root, "slug", None)
    if not slug:
        return None  # ✅ no pk fallback here

    # 4) Mode + section
    mode = _guess_mode_for_obj(root)
    section = guess_entry_section(ct_key)

    return build_content_link(
        slug=str(slug),
        section=section,
        focus=focus,
        mode=mode,
    )



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

    # Resolve user preference + channel mask
    enabled, channels_mask = _is_enabled(recipient, notif_type)

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

    # Prefer explicit link, else smart UI link, else get_absolute_url fallback
    link = link or _smart_ui_link(target_obj, action_obj, extra_payload) or _resolve_link(target_obj, action_obj)

    dedupe_key = (
        f"{recipient.id}:{actor.id if actor else 0}:"
        f"{notif_type}:{action_id or 0}:{target_id or 0}"
    )

    def _persist():
        try:
            if dedupe:
                notif, created = Notification.objects.get_or_create(
                    dedupe_key=dedupe_key,
                    defaults=dict(
                        user=recipient,
                        actor=actor,
                        message=message,
                        notification_type=notif_type,
                        target_content_type=target_ct,
                        target_object_id=target_id,
                        action_content_type=action_ct,
                        action_object_id=action_id,
                        link=link,
                    ),
                )
                if created:
                    _deliver_notification(notif, channels_mask, extra_payload)
                else:
                    logger.info("[Notif] Dedup hit → notif_id=%s dedupe_key=%s", notif.id, dedupe_key)
                return notif

            # old behavior
            notif = Notification.objects.create(...)
            _deliver_notification(notif, channels_mask, extra_payload)
            return notif

        except Exception as e:
            logger.error(..., exc_info=True)
            return None

    if transaction.get_connection().in_atomic_block:
        logger.warning("[Notif] in_atomic → scheduling on_commit (type=%s user=%s)", notif_type, recipient.id)
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
    try:
        if channels_mask & CHANNEL_WS:
            layer = get_channel_layer()
            if not layer:
                logger.warning("[Notif] No channel_layer; skipping WS")
                return

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

            group_name = f"notif_user_{notif.user_id}"
            logger.info(
                "[Notif] WS about to send → group=%s payload=%s",
                group_name,
                payload,
            )

            async_to_sync(layer.group_send)( 
                group_name,
                {
                    "type": "dispatch_event",
                    "app": "notifications",
                    "event": "notification",
                    "data": payload,
                },
            )

            logger.info(
                "[Notif] WS sent to group %s OK",
                group_name,
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

            # FCM requires all values to be strings
            safe_data = {}
            for key, value in base_data.items():
                safe_data[key] = "" if value is None else str(value)

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
        logger.info(
            "[Notif] EMAIL DECISION → notif_id=%s type=%s mask=%s email=%s",
            notif.id,
            notif.notification_type,
            channels_mask,
            getattr(notif.user, "email", None),
        )

        if channels_mask & CHANNEL_EMAIL:
            email = getattr(notif.user, "email", None)
            if not email:
                logger.info("[Notif] No email for user %s (notif %s)", notif.user_id, notif.id)
                return

            subject = "New Notification from TownLIT"
            body_text = f"{notif.message}"

            res = send_email_notification.delay(
                email,
                subject,
                body_text,
                notif.link,
            )

            logger.info(
                "[Notif] Email task queued → notif_id=%s task_id=%s to=%s",
                notif.id,
                getattr(res, "id", None),
                email,
            )

    except Exception as e:
        logger.warning(
            "[Notif] Email delivery failed for user %s notif %s: %s",
            notif.user_id,
            notif.id,
            e,
            exc_info=True,
        )
