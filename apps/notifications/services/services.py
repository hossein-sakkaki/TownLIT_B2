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
    ENTRY_BY_CT,
    build_content_link,
    build_friendship_request_link,
    guess_entry_section,
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

def _resolve_relationship_ui_link(
    *,
    notif_type: str,
    target_obj=None,
    action_obj=None,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Build precise relationship deep links.

    Friendship request notifications must include the friendship/request ID
    so iOS can open and highlight the exact request row.
    """
    if notif_type != "friend_request_received":
        return None

    payload = (
        extra_payload
        if isinstance(extra_payload, dict)
        else {}
    )

    relationship_obj = action_obj or target_obj

    friendship_id = (
        payload.get("request_id")
        or payload.get("friendship_id")
        or getattr(relationship_obj, "pk", None)
        or getattr(relationship_obj, "id", None)
    )

    if not friendship_id:
        logger.warning(
            "[Notif][FriendshipLink] Missing friendship ID type=%s",
            notif_type,
        )
        return None

    from_user = getattr(
        relationship_obj,
        "from_user",
        None,
    )

    user_id = (
        payload.get("from_user_id")
        or payload.get("user_id")
        or getattr(
            relationship_obj,
            "from_user_id",
            None,
        )
        or getattr(
            from_user,
            "id",
            None,
        )
    )

    username = (
        payload.get("from_username")
        or payload.get("username")
        or getattr(
            from_user,
            "username",
            None,
        )
    )

    request_kind = (
        payload.get("request_kind")
        or "received"
    )

    resolved_link = build_friendship_request_link(
        friendship_id=int(friendship_id),
        user_id=(
            int(user_id)
            if user_id is not None
            else None
        ),
        username=(
            str(username).strip()
            if username
            else None
        ),
        request_kind=str(request_kind),
    )

    logger.info(
        "[Notif][FriendshipLink] Resolved link type=%s friendship=%s user=%s link=%s",
        notif_type,
        friendship_id,
        user_id,
        resolved_link,
    )

    return resolved_link

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

    if notification_type == "testimony_video_needs_review":
        return "Your TownLIT video testimony is being reviewed"

    if notification_type == "testimony_video_approved":
        return "Your TownLIT video testimony was approved"

    return "New Notification from TownLIT"

def _push_title_for_notification(
    notification_type: str,
) -> str:
    """
    Pick a clear push title.
    """
    if notification_type == "testimony_video_rejected":
        return "Video testimony not accepted"

    if notification_type == "testimony_video_needs_review":
        return "Video testimony under review"

    if notification_type == "testimony_video_approved":
        return "Video testimony approved"

    if notification_type == "new_message_direct":
        return "New message"

    if notification_type == "new_message_group":
        return "New group message"

    if notification_type == "messenger_group_created":
        return "New group"

    if notification_type == "messenger_message_pinned":
        return "Pinned message"

    if notification_type in {
        "messenger_reaction_direct",
        "messenger_reaction_group",
    }:
        return "New reaction"

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

    if notification_type == "testimony_video_needs_review":
        return (
            "Your video testimony was uploaded and is waiting for review "
            "before it appears in Square or Stream."
        )

    if notification_type == "testimony_video_approved":
        return (
            "Your video testimony was approved and may now appear in "
            "Square or Stream."
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


def _should_retry_push_without_sound(error: Exception) -> bool:
    """
    Some push providers reject payloads with invalid custom sound names.

    If this happens, retry once without a custom sound so push delivery does
    not fully break because of a missing .caf file in the iOS bundle.
    """
    raw = str(error or "").lower()

    sound_error_markers = {
        "sound",
        "badsound",
        "bad sound",
        "invalid sound",
        "invalid payload",
        "badpayload",
        "bad payload",
    }

    return any(marker in raw for marker in sound_error_markers)


def _safe_push_data(data: Dict[str, Any]) -> Dict[str, str]:
    """
    APNs/FCM data payload values must be strings.
    """
    safe_data = {}

    for key, value in (data or {}).items():
        safe_data[str(key)] = "" if value is None else str(value)

    return safe_data


def _send_firebase_push_safely(
    *,
    recipient,
    title: str,
    body: str,
    data: Dict[str, str],
    context: str,
    notif_type: str,
) -> bool:
    """
    Send Firebase/Web push and log the real result.
    """
    try:
        result = push_engine.send_to_user(
            recipient,
            title=title,
            body=body,
            data=data,
        )

        # Some engines return None on success.
        return True

    except Exception as e:
        logger.warning(
            "[Notif][Push][Firebase] failed context=%s user=%s type=%s error=%s",
            context,
            getattr(recipient, "id", None),
            notif_type,
            e,
            exc_info=True,
        )
        return False


def _send_apns_push_safely(
    *,
    recipient,
    title: str,
    body: str,
    data: Dict[str, str],
    badge: int,
    sound: str | None,
    context: str,
    notif_type: str,
) -> bool:
    """
    Send APNs push and retry once without custom sound if sound payload fails.
    """
    try:
        result = apns_engine.send_to_user(
            recipient,
            title=title,
            body=body,
            data=data,
            badge=badge,
            sound=sound,
        )

        return True

    except Exception as first_error:
        logger.warning(
            "[Notif][Push][APNs] failed context=%s user=%s type=%s sound=%s error=%s",
            context,
            getattr(recipient, "id", None),
            notif_type,
            sound,
            first_error,
            exc_info=True,
        )

        if sound and _should_retry_push_without_sound(first_error):
            try:
                result = apns_engine.send_to_user(
                    recipient,
                    title=title,
                    body=body,
                    data=data,
                    badge=badge,
                    sound=None,
                )

                return True

            except Exception as retry_error:
                logger.warning(
                    "[Notif][Push][APNs] retry without sound failed context=%s user=%s type=%s error=%s",
                    context,
                    getattr(recipient, "id", None),
                    notif_type,
                    retry_error,
                    exc_info=True,
                )

        return False
    
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
        return False

    enabled, channels_mask = _is_enabled(recipient, notif_type)

    if not enabled:
        return False

    # Push-only means no DB, no WS, no Email.
    channels_mask = int(channels_mask or 0) & CHANNEL_PUSH

    if not (channels_mask & CHANNEL_PUSH):
        logger.warning(
            "[Notif][PushOnly] CHANNEL_PUSH missing after mask user=%s type=%s mask=%s",
            getattr(recipient, "id", None),
            notif_type,
            channels_mask,
        )
        return False

    delivery_decision = apply_relationship_delivery_policy(
        recipient=recipient,
        actor=actor,
        channels_mask=channels_mask,
    )

    if not delivery_decision.persist:
        return False

    channels_mask = int(delivery_decision.channels_mask or 0) & CHANNEL_PUSH

    if not (channels_mask & CHANNEL_PUSH):
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

    safe_data = _safe_push_data(base_data)

    push_title = _push_title_for_notification(notif_type)
    push_body = _push_body_for_notification(notif_type, message)
    push_sound = _push_sound_for_notification(notif_type)
    badge_count = _badge_count_for_user(recipient)

    firebase_sent = _send_firebase_push_safely(
        recipient=recipient,
        title=push_title,
        body=push_body,
        data=safe_data,
        context="push_only",
        notif_type=notif_type,
    )

    apns_sent = _send_apns_push_safely(
        recipient=recipient,
        title=push_title,
        body=push_body,
        data=safe_data,
        badge=badge_count,
        sound=push_sound,
        context="push_only",
        notif_type=notif_type,
    )

    sent_any = firebase_sent or apns_sent

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
    Centralized notification creation and delivery.

    Delivery:
    - Database
    - WebSocket
    - Push
    - Email

    Relationship policy:
    - Boundary suppresses the notification completely.
    - Stillness keeps the database notification but suppresses
      WebSocket, Push, and Email.
    """

    if not recipient:
        logger.warning(
            "[Notif] Missing recipient; notification skipped."
        )
        return None

    if (
        actor
        and getattr(actor, "id", None)
        == getattr(recipient, "id", None)
    ):
        return None

    enabled, channels_mask = _is_enabled(
        recipient,
        notif_type,
    )

    if notif_type in NOTIFICATION_TYPES_PUSH_EMAIL_ONLY:
        channels_mask &= (
            CHANNEL_PUSH
            | CHANNEL_EMAIL
        )

    if notif_type in NOTIFICATION_TYPES_NO_EMAIL:
        channels_mask &= ~CHANNEL_EMAIL

    if not enabled:
        logger.info(
            "[Notif] Notification disabled by preference "
            "user=%s type=%s",
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
            "[Notif] Suppressed by relationship policy "
            "user=%s actor=%s type=%s reason=%s",
            getattr(recipient, "id", None),
            getattr(actor, "id", None),
            notif_type,
            delivery_decision.reason,
        )
        return None

    channels_mask = delivery_decision.channels_mask

    # ------------------------------------------------------------
    # Generic relation metadata
    # ------------------------------------------------------------
    target_ct = _safe_ct(target_obj)
    target_id = getattr(
        target_obj,
        "pk",
        None,
    )

    action_ct = _safe_ct(action_obj)
    action_id = getattr(
        action_obj,
        "pk",
        None,
    )

    # ------------------------------------------------------------
    # Resolve frontend link
    #
    # Priority:
    # 1. Explicit caller-provided link
    # 2. Precise relationship link
    # 3. Smart content link
    # 4. Model get_absolute_url()
    # ------------------------------------------------------------
    explicit_link = (
        link.strip()
        if isinstance(link, str)
        and link.strip()
        else None
    )

    relationship_link = _resolve_relationship_ui_link(
        notif_type=notif_type,
        target_obj=target_obj,
        action_obj=action_obj,
        extra_payload=extra_payload,
    )

    smart_content_link = _smart_ui_link(
        target_obj,
        action_obj,
        extra_payload,
    )

    fallback_link = _resolve_link(
        target_obj,
        action_obj,
    )

    resolved_link = (
        explicit_link
        or relationship_link
        or smart_content_link
        or fallback_link
        or ""
    )

    logger.info(
        "[Notif] Link resolved "
        "type=%s recipient=%s target=%s action=%s link=%s",
        notif_type,
        getattr(recipient, "id", None),
        target_id,
        action_id,
        resolved_link,
    )

    dedupe_key = (
        f"{recipient.id}:"
        f"{actor.id if actor else 0}:"
        f"{notif_type}:"
        f"{action_id or 0}:"
        f"{target_id or 0}"
    )

    def _persist():
        try:
            if dedupe:
                notif, created = Notification.objects.get_or_create(
                    dedupe_key=dedupe_key,
                    defaults={
                        "user": recipient,
                        "actor": actor,
                        "message": message,
                        "notification_type": notif_type,
                        "target_content_type": target_ct,
                        "target_object_id": target_id,
                        "action_content_type": action_ct,
                        "action_object_id": action_id,
                        "link": resolved_link,
                    },
                )

                if created:
                    logger.info(
                        "[Notif] Created notification "
                        "id=%s type=%s link=%s",
                        notif.id,
                        notif_type,
                        notif.link,
                    )

                    _deliver_notification(
                        notif,
                        channels_mask,
                        extra_payload,
                    )

                    return notif

                # Keep an existing deduplicated record synchronized with
                # the newest precise link and message, without re-delivery.
                update_fields = []

                if notif.link != resolved_link:
                    notif.link = resolved_link
                    update_fields.append("link")

                if notif.message != message:
                    notif.message = message
                    update_fields.append("message")

                if update_fields:
                    notif.save(
                        update_fields=update_fields
                    )

                    logger.info(
                        "[Notif] Dedup record updated "
                        "notif_id=%s fields=%s link=%s",
                        notif.id,
                        update_fields,
                        notif.link,
                    )
                else:
                    logger.info(
                        "[Notif] Dedup hit "
                        "notif_id=%s dedupe_key=%s",
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
                link=resolved_link,
            )

            logger.info(
                "[Notif] Created non-deduplicated notification "
                "id=%s type=%s link=%s",
                notif.id,
                notif_type,
                notif.link,
            )

            _deliver_notification(
                notif,
                channels_mask,
                extra_payload,
            )

            return notif

        except Exception:
            logger.error(
                "[Notif] Failed to create/deliver notification "
                "user=%s actor=%s type=%s",
                getattr(recipient, "id", None),
                getattr(actor, "id", None),
                notif_type,
                exc_info=True,
            )
            return None

    if transaction.get_connection().in_atomic_block:
        transaction.on_commit(
            lambda: _persist()
        )
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

                async_to_sync(layer.group_send)(
                    group_name,
                    {
                        "type": "dispatch_event",
                        "app": "notifications",
                        "event": "notification",
                        "data": payload,
                    },
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
                        "[Notif][Push] extra_payload merge failed notif=%s error=%s",
                        notif.id,
                        e,
                        exc_info=True,
                    )

            safe_data = _safe_push_data(base_data)

            push_title = _push_title_for_notification(notif.notification_type)
            push_body = _push_body_for_notification(
                notif.notification_type,
                notif.message,
            )
            push_sound = _push_sound_for_notification(notif.notification_type)
            badge_count = _badge_count_for_user(notif.user)

            firebase_sent = _send_firebase_push_safely(
                recipient=notif.user,
                title=push_title,
                body=push_body,
                data=safe_data,
                context="stored_notification",
                notif_type=notif.notification_type,
            )

            apns_sent = _send_apns_push_safely(
                recipient=notif.user,
                title=push_title,
                body=push_body,
                data=safe_data,
                badge=badge_count,
                sound=push_sound,
                context="stored_notification",
                notif_type=notif.notification_type,
            )

    except Exception as e:
        logger.warning(
            "[Notif][Push] delivery wrapper failed user=%s notif=%s error=%s",
            getattr(notif, "user_id", None),
            getattr(notif, "id", None),
            e,
            exc_info=True,
        )

    # ------------------------------------------------------------------
    # 3) Email Delivery
    # ------------------------------------------------------------------
    try:
        if channels_mask & CHANNEL_EMAIL:
            email = getattr(notif.user, "email", None)
            if not email:
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

    except Exception as e:
        logger.warning(
            "[Notif] Email delivery failed for user %s notif %s: %s",
            notif.user_id,
            notif.id,
            e,
            exc_info=True,
        )

