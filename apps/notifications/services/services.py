# apps/notifications/services/services.py

import logging
from typing import Optional
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from typing import Optional, Dict, Any

from utils.firebase.push_engine import push_engine  # NEW: Firebase REST engine
from utils.apple.apns_engine import apns_engine  # NEW: Apple APNs engine
from apps.notifications.models import Notification, UserNotificationPreference
from apps.notifications.constants import (
    CHANNEL_PUSH,
    CHANNEL_WS,
    CHANNEL_EMAIL,
    CHANNEL_DEFAULT,
    NOTIFICATION_TYPES_PUSH_EMAIL_ONLY,
    NOTIFICATION_TYPES_NO_EMAIL,
    NOTIFICATION_TYPES_FORCE_ENABLED,
    NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD,
    NOTIFICATION_TYPES_PUSH_ONLY,
    sanitize_notification_channels,
    notification_default_channels,
)
from apps.notifications.services.ui_link_resolver import (
    build_content_link,
    guess_entry_section, 
    ENTRY_BY_CT
)
from apps.notifications.services.delivery_policy import (
    apply_relationship_delivery_policy,
)

from apps.notifications.tasks import send_email_notification  # Celery async task

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Check if notification type is enabled for user
# -------------------------------------------------------------------------
def _is_enabled(user, notif_type):
    """
    Return notification preference state.

    Messenger notification types are intentionally not controlled by
    general notification preferences. They should later be controlled by
    conversation-level mute/silence settings.

    Channel masks are always sanitized so old DB rows or old clients cannot
    re-enable unsupported email delivery.
    """
    if notif_type in NOTIFICATION_TYPES_FORCE_ENABLED:
        return True, sanitize_notification_channels(
            notif_type,
            notification_default_channels(notif_type),
        )

    try:
        pref = UserNotificationPreference.objects.get(
            user=user,
            notification_type=notif_type,
        )

        channels_mask = sanitize_notification_channels(
            notif_type,
            pref.channels_mask if pref.enabled else 0,
        )

        if pref.channels_mask != channels_mask:
            pref.channels_mask = channels_mask
            pref.save(update_fields=["channels_mask"])

        return pref.enabled, channels_mask

    except UserNotificationPreference.DoesNotExist:
        return True, sanitize_notification_channels(
            notif_type,
            notification_default_channels(notif_type),
        )
    

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


def _owner_user_for_content_obj(obj):
    """
    Resolve the user who owns a content object.

    This is intentionally generic because notifications work with Moment,
    Prayer, Testimony, and future content models without direct imports.
    """
    if not obj:
        return None

    for attr in (
        "user",
        "owner",
        "author",
        "created_by",
        "name",
        "member_user",
        "org_owner_user",
    ):
        val = getattr(obj, attr, None)

        if val is not None and hasattr(val, "id"):
            return val

    try:
        inner = getattr(obj, "content_object", None)

        if inner:
            for attr in (
                "user",
                "owner",
                "author",
                "created_by",
                "member_user",
                "org_owner_user",
            ):
                val = getattr(inner, attr, None)

                if val is not None and hasattr(val, "id"):
                    return val

    except Exception:
        return None

    return None


def _owner_username_for_content_obj(obj) -> str | None:
    """
    Return the content owner's username for iOS profile-scoped routing.

    Web continues to use /content/<slug>; iOS can use this hint to open the
    same content through VisitorProfileContainerView.
    """
    user = _owner_user_for_content_obj(obj)
    username = getattr(user, "username", None)

    if isinstance(username, str) and username.strip():
        return username.strip()

    return None


def _profile_key_path_for_content_obj(obj, ct_key: str) -> str | None:
    """
    Return the profile viewer key path used by iOS.

    Examples:
    - moments.image
    - moments.video
    - prayers.image
    - prayers.video
    - testimonies.written
    - testimonies.audio
    - testimonies.video
    """
    if not obj:
        return None

    if ct_key == "posts.moment":
        return "moments.video" if getattr(obj, "video", None) else "moments.image"

    if ct_key == "posts.prayer":
        return "prayers.video" if getattr(obj, "video", None) else "prayers.image"

    if ct_key == "posts.testimony":
        raw_type = (getattr(obj, "type", "") or "").strip().lower()

        if raw_type in {"audio", "voice"}:
            return "testimonies.audio"

        if raw_type == "video":
            return "testimonies.video"

        return "testimonies.written"

    return None


def _smart_ui_link(target_obj, action_obj, extra_payload: dict | None) -> str | None:
    """
    Build a universal /content deep-link for supported content types.

    Important:
    - Web uses /content/<slug> directly.
    - iOS currently opens content through profile-scoped routing, so we also
      include non-breaking hints:
        u = owner username
        k = profile key path
    - For comment/reply/reaction notifications, focus remains the interaction
      target, for example:
        comment-123
        reply-456:parent-123
        reaction-789
    """

    # 0) Resolve root content from action when the action is Comment/Reaction.
    root = _resolve_root_content_from_action(action_obj) or target_obj

    if not root:
        return None

    # 1) Only build /content links for explicitly registered content models.
    ct_key = _ct_key_for_obj(root) or ""

    if ct_key not in ENTRY_BY_CT:
        return None

    # 2) Build interaction focus.
    comment_id = parent_id = reaction_id = None

    if isinstance(extra_payload, dict):
        comment_id = extra_payload.get("comment_id")
        parent_id = extra_payload.get("parent_id")
        reaction_id = extra_payload.get("reaction_id")

    focus = None

    if comment_id:
        focus = (
            f"reply-{comment_id}:parent-{parent_id}"
            if parent_id
            else f"comment-{comment_id}"
        )
    elif reaction_id:
        focus = f"reaction-{reaction_id}"

    # 3) Content slug is required. Do not fallback to pk here.
    slug = getattr(root, "slug", None)

    if not slug:
        return None

    # 4) Mode + section for web.
    mode = _guess_mode_for_obj(root)
    section = guess_entry_section(ct_key)

    # 5) Extra iOS-safe hints. Web can ignore these.
    owner_username = _owner_username_for_content_obj(root)
    key_path = _profile_key_path_for_content_obj(root, ct_key)

    extra_link_params = {}

    if isinstance(extra_payload, dict):
        if extra_payload.get("comment_id"):
            extra_link_params["comment_id"] = extra_payload.get("comment_id")

        if extra_payload.get("parent_id"):
            extra_link_params["parent_id"] = extra_payload.get("parent_id")

        if extra_payload.get("reaction_id"):
            extra_link_params["reaction_id"] = extra_payload.get("reaction_id")

        if extra_payload.get("reaction_type"):
            extra_link_params["reaction_type"] = extra_payload.get("reaction_type")

    return build_content_link(
        slug=str(slug),
        section=section,
        focus=focus,
        mode=mode,
        owner_username=owner_username,
        key_path=key_path,
        extra_params=extra_link_params,
    )

def _email_subject_for_notification(
    notification_type: str,
) -> str:
    """
    Pick a clear email subject for important notification types.
    """
    if notification_type == "testimony_video_rejected":
        return "Your TownLIT video testimony was not accepted"

    return "New Notification from TownLIT"

def _push_title_for_notification(
    notification_type: str,
) -> str:
    """
    Pick a clear push title.
    """
    if notification_type == "testimony_video_rejected":
        return "Video testimony not accepted"

    if notification_type == "new_message_direct":
        return "New message"

    if notification_type == "new_message_group":
        return "New group message"

    return "TownLIT Notification"

def _push_body_for_notification(
    notification_type: str,
    message: str,
) -> str:
    """
    Push body should be shorter than the full in-app/email message.
    """
    if notification_type == "testimony_video_rejected":
        return (
            "Your video did not appear to be a personal testimony. "
            "You can upload a new testimony from your profile."
        )

    clean = (message or "").strip()
    if len(clean) > 180:
        return clean[:177] + "..."

    return clean

def _push_sound_for_notification(
    notification_type: str,
) -> str:
    """
    Pick the APNs custom sound file for iOS.

    The returned file name must exactly match a .caf file included
    in the iOS app bundle under Copy Bundle Resources.
    """
    if notification_type in {"new_message_direct", "new_message_group"}:
        return "townlit_message.caf"

    return "townlit_notify.caf"

def _general_unread_notification_count_for_user(user) -> int:
    """
    Count unread non-messenger notifications.

    Messenger notification records are excluded because Messenger unread
    count comes from Dialogue unread messages.
    """
    if not user:
        return 0

    try:
        return max(
            Notification.objects.filter(
                user=user,
                is_read=False,
            )
            .exclude(
                notification_type__in=NOTIFICATION_TYPES_EXCLUDED_FROM_GENERAL_UNREAD
            )
            .count(),
            0,
        )
    except Exception:
        logger.warning(
            "[Notif] Failed to calculate general unread notification count user=%s",
            getattr(user, "id", None),
            exc_info=True,
        )
        return 0


def _messenger_unread_count_for_user(user) -> int:
    """
    Count unread messenger messages using the same source as the
    conversation unread-counts API.

    This intentionally uses Dialogue.unread_messages_for_user(user)
    to stay consistent with DialogueViewSet.get_unread_counts.
    """
    if not user:
        return 0

    try:
        from apps.conversation.models import Dialogue

        dialogues = (
            Dialogue.objects
            .filter(participants=user)
            .exclude(deleted_by_users=user)
        )

        total = 0

        for dialogue in dialogues:
            total += dialogue.unread_messages_for_user(user).count()

        return max(int(total), 0)

    except Exception:
        logger.warning(
            "[Notif] Failed to calculate messenger unread count user=%s",
            getattr(user, "id", None),
            exc_info=True,
        )
        return 0


def _badge_count_for_user(user) -> int:
    """
    Calculate the iOS app icon badge count.

    Badge = unread general notifications + unread messenger messages.
    """
    general_count = _general_unread_notification_count_for_user(user)
    messenger_count = _messenger_unread_count_for_user(user)

    total = general_count + messenger_count

    logger.debug(
        "[Notif] Badge count calculated user=%s general=%s messenger=%s total=%s",
        getattr(user, "id", None),
        general_count,
        messenger_count,
        total,
    )

    return max(int(total), 0)


# -------------------------------------------------------------------------
# Push-only notification dispatch (no DB, no WS, no Email)
# -------------------------------------------------------------------------
def dispatch_push_only_notification(
    *,
    recipient,
    actor=None,
    notif_type: str,
    message: str,
    link: Optional[str] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
):
    """
    Send push-only notifications without creating a Notification row.

    Used for Messenger:
    - no Notification Center item
    - no notification WebSocket item
    - no email
    - push only
    """
    if not recipient:
        logger.warning("[Notif][PushOnly] Missing recipient; skipped.")
        return False

    if actor and getattr(actor, "id", None) == getattr(recipient, "id", None):
        logger.debug(
            "[Notif][PushOnly] Self notification skipped actor=%s type=%s",
            getattr(actor, "id", None),
            notif_type,
        )
        return False

    enabled, channels_mask = _is_enabled(recipient, notif_type)

    if not enabled:
        logger.info(
            "[Notif][PushOnly] Disabled by preference user=%s type=%s",
            getattr(recipient, "id", None),
            notif_type,
        )
        return False

    # Push-only means no DB, no WS, no Email.
    channels_mask = channels_mask & CHANNEL_PUSH

    delivery_decision = apply_relationship_delivery_policy(
        recipient=recipient,
        actor=actor,
        channels_mask=channels_mask,
    )

    if not delivery_decision.persist:
        logger.info(
            "[Notif][PushOnly] Suppressed by relationship policy user=%s actor=%s type=%s reason=%s",
            getattr(recipient, "id", None),
            getattr(actor, "id", None),
            notif_type,
            delivery_decision.reason,
        )
        return False

    channels_mask = delivery_decision.channels_mask & CHANNEL_PUSH

    if not (channels_mask & CHANNEL_PUSH):
        logger.info(
            "[Notif][PushOnly] Push channel suppressed user=%s actor=%s type=%s reason=%s",
            getattr(recipient, "id", None),
            getattr(actor, "id", None),
            notif_type,
            delivery_decision.reason,
        )
        return False

    resolved_link = link or ""

    base_data = {
        "link": resolved_link,
        "deep_link": resolved_link,
        "url": resolved_link,
        "notification_type": notif_type,
        "notification_id": "",
    }

    if extra_payload:
        try:
            base_data.update(extra_payload)
        except Exception:
            logger.warning(
                "[Notif][PushOnly] extra_payload merge failed user=%s type=%s",
                getattr(recipient, "id", None),
                notif_type,
                exc_info=True,
            )

    safe_data = {
        str(key): "" if value is None else str(value)
        for key, value in base_data.items()
    }

    push_title = _push_title_for_notification(notif_type)
    push_body = _push_body_for_notification(notif_type, message)

    sent_any = False

    try:
        push_engine.send_to_user(
            recipient,
            title=push_title,
            body=push_body,
            data=safe_data,
        )

        sent_any = True

        logger.debug(
            "[Notif][PushOnly] Firebase push dispatched user=%s type=%s",
            getattr(recipient, "id", None),
            notif_type,
        )

    except Exception as e:
        logger.warning(
            "[Notif][PushOnly] Firebase push failed user=%s type=%s error=%s",
            getattr(recipient, "id", None),
            notif_type,
            e,
            exc_info=True,
        )

    try:
        apns_engine.send_to_user(
            recipient,
            title=push_title,
            body=push_body,
            data=safe_data,
            badge=_badge_count_for_user(recipient),
            sound=_push_sound_for_notification(notif_type),
        )

        sent_any = True

        logger.debug(
            "[Notif][PushOnly] APNs push dispatched user=%s type=%s",
            getattr(recipient, "id", None),
            notif_type,
        )

    except Exception as e:
        logger.warning(
            "[Notif][PushOnly] APNs push failed user=%s type=%s error=%s",
            getattr(recipient, "id", None),
            notif_type,
            e,
            exc_info=True,
        )

    logger.info(
        "[Notif][PushOnly] Done user=%s actor=%s type=%s sent_any=%s link=%s",
        getattr(recipient, "id", None),
        getattr(actor, "id", None),
        notif_type,
        sent_any,
        resolved_link,
    )

    return sent_any


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

    Relationship policy:
    - Boundary suppresses notification completely.
    - Stillness keeps DB notification but suppresses WS/Push/Email.
    """

    if not recipient:
        logger.warning("[Notif] Missing recipient; notification skipped.")
        return None

    if actor and getattr(actor, "id", None) == getattr(recipient, "id", None):
        logger.debug(
            "[Notif] Self notification skipped actor=%s type=%s",
            getattr(actor, "id", None),
            notif_type,
        )
        return None

    # Resolve user preference + channel mask
    enabled, channels_mask = _is_enabled(recipient, notif_type)

    # For some types, only Push + Email are allowed, no WS.
    if notif_type in NOTIFICATION_TYPES_PUSH_EMAIL_ONLY:
        channels_mask = channels_mask & (CHANNEL_PUSH | CHANNEL_EMAIL)

    # Messenger notifications must never send email.
    # They may still use DB persistence, WebSocket, and Push.
    if notif_type in NOTIFICATION_TYPES_NO_EMAIL:
        channels_mask = channels_mask & ~CHANNEL_EMAIL

    if not enabled:
        logger.info(
            "[Notif] Notification disabled by preference → user=%s type=%s",
            recipient.id,
            notif_type,
        )
        return None

    # ------------------------------------------------------------
    # Boundary / Stillness policy
    # ------------------------------------------------------------
    delivery_decision = apply_relationship_delivery_policy(
        recipient=recipient,
        actor=actor,
        channels_mask=channels_mask,
    )

    if not delivery_decision.persist:
        logger.info(
            "[Notif] Suppressed by relationship policy → user=%s actor=%s type=%s reason=%s",
            getattr(recipient, "id", None),
            getattr(actor, "id", None),
            notif_type,
            delivery_decision.reason,
        )
        return None

    channels_mask = delivery_decision.channels_mask

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
                    logger.info(
                        "[Notif] Created → notif_id=%s user=%s actor=%s type=%s policy=%s mask=%s",
                        notif.id,
                        recipient.id,
                        getattr(actor, "id", None),
                        notif_type,
                        delivery_decision.reason,
                        channels_mask,
                    )
                    _deliver_notification(notif, channels_mask, extra_payload)
                else:
                    logger.info(
                        "[Notif] Dedup hit → notif_id=%s dedupe_key=%s",
                        notif.id,
                        dedupe_key,
                    )

                return notif

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
            )

            logger.info(
                "[Notif] Created no-dedupe → notif_id=%s user=%s actor=%s type=%s policy=%s mask=%s",
                notif.id,
                recipient.id,
                getattr(actor, "id", None),
                notif_type,
                delivery_decision.reason,
                channels_mask,
            )

            _deliver_notification(notif, channels_mask, extra_payload)
            return notif

        except Exception:
            logger.error(
                "[Notif] Failed to create/deliver notification user=%s actor=%s type=%s",
                getattr(recipient, "id", None),
                getattr(actor, "id", None),
                notif_type,
                exc_info=True,
            )
            return None

    if transaction.get_connection().in_atomic_block:
        logger.debug(
            "[Notif] in_atomic → scheduling on_commit type=%s user=%s",
            notif_type,
            recipient.id,
        )
        transaction.on_commit(lambda: _persist())
        return None

    return _persist()



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

            if not layer:
                logger.warning("[Notif] No channel_layer; skipping WS")
            else:
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
    # 2) Push Delivery (Firebase REST + APNs)
    # ------------------------------------------------------------------
    try:
        if channels_mask & CHANNEL_PUSH:

            resolved_link = notif.link or ""

            base_data = {
                "link": resolved_link,
                "deep_link": resolved_link,
                "url": resolved_link,
                "notification_type": notif.notification_type,
                "notification_id": str(notif.id),
            }

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

            safe_data = {}
            for key, value in base_data.items():
                safe_data[key] = "" if value is None else str(value)

            push_title = _push_title_for_notification(notif.notification_type)
            push_body = _push_body_for_notification(
                notif.notification_type,
                notif.message,
            )

            # Web / Firebase push
            try:
                push_engine.send_to_user(
                    notif.user,
                    title=push_title,
                    body=push_body,
                    data=safe_data,
                )

                logger.debug(
                    "[Notif] Push dispatched via Firebase REST for user %s",
                    notif.user_id,
                )

            except Exception as e:
                logger.warning(
                    "[Notif] Firebase push delivery failed for user %s: %s",
                    notif.user_id,
                    e,
                    exc_info=True,
                )

            # Native iOS / APNs push
            try:
                apns_engine.send_to_user(
                    notif.user,
                    title=push_title,
                    body=push_body,
                    data=safe_data,
                    badge=_badge_count_for_user(notif.user),
                    sound=_push_sound_for_notification(notif.notification_type),
                )

                logger.debug(
                    "[Notif] Push dispatched via APNs for user %s",
                    notif.user_id,
                )

            except Exception as e:
                logger.warning(
                    "[Notif] APNs push delivery failed for user %s: %s",
                    notif.user_id,
                    e,
                    exc_info=True,
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

            subject = _email_subject_for_notification(notif.notification_type)
            body_text = f"{notif.message}"

            email_link = None
            if isinstance(extra_payload, dict):
                email_link = extra_payload.get("email_link") or extra_payload.get("web_link")

            email_link = email_link or notif.link

            res = send_email_notification.delay(
                email,
                subject,
                body_text,
                email_link,
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
