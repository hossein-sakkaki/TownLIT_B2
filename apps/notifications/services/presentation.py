# apps/notifications/services/presentation.py

from __future__ import annotations

from typing import Any, Mapping


REACTION_LABELS = {
    "like": "Like",
    "bless": "Bless",
    "gratitude": "Gratitude",
    "amen": "Amen",
    "encouragement": "Encouragement",
    "empathy": "Empathy",
    "faithfire": "FaithFire",
    "support": "Support",
}


STATIC_PUSH_TITLES = {
    # Comments
    "new_comment": "New comment",
    "new_reply": "Reply to your comment",
    "new_reply_post_owner": "New reply on your post",

    # Friendships
    "friend_request_received": "New friend request",
    "friend_request_accepted": "Friend request accepted",
    "friend_request_declined": "Friend request declined",
    "friend_request_cancelled": "Friend request cancelled",
    "friendship_deleted": "Removed from friends",

    # LITCovenant
    "fellowship_request_received": "New LITCovenant request",
    "fellowship_request_accepted": "LITCovenant request accepted",
    "fellowship_request_confirmed": "LITCovenant confirmed",
    "fellowship_request_declined": "LITCovenant request declined",
    "fellowship_decline_notice": "LITCovenant response recorded",
    "fellowship_cancelled": "LITCovenant cancelled",

    # Messenger events
    "messenger_group_created": "Added to a group",
    "messenger_message_pinned": "Message pinned",
    "messenger_reaction_direct": "Reaction to your message",
    "messenger_reaction_group": "Reaction to your group message",

    # Testimonies
    "new_testimony_written": "New written Testimony",
    "new_testimony_audio": "New audio Testimony",
    "new_testimony_video": "New video Testimony",
    "testimony_video_rejected": "Video Testimony not accepted",
    "testimony_video_needs_review": "Video Testimony under review",
    "testimony_video_approved": "Video Testimony approved",

    # Sanctuary
    "sanctuary_admin_assignment": "Sanctuary case assigned",
    "sanctuary_member_review_request": "Sanctuary review requested",
    "sanctuary_outcome_finalized": "Sanctuary outcome finalized",
    "sanctuary_appeal_assignment": "Sanctuary appeal assigned",

    # Moments
    "new_moment_image": "New Moment",
    "new_moment_video": "New video Moment",

    # Prayers
    "new_prayer_image": "New Prayer request",
    "new_prayer_video": "New video Prayer request",
    "prayer_result_answered": "Prayer answered",
    "prayer_result_not_answered": "Prayer follow-up",

    # Journey
    "new_journey": "New Journey update",
}


TESTIMONY_STATUS_PUSH_BODIES = {
    "testimony_video_rejected": (
        "Your video did not appear to be a personal Testimony. "
        "You can upload a new one from your profile."
    ),
    "testimony_video_needs_review": (
        "Your video Testimony is waiting for review before it appears "
        "in Square or Stream."
    ),
    "testimony_video_approved": (
        "Your video Testimony was approved and may now appear in "
        "Square or Stream."
    ),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _payload(extra_payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return extra_payload if isinstance(extra_payload, Mapping) else {}


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    return _clean(value).lower() in {"1", "true", "yes"}


def actor_name(actor) -> str:
    """Return a short, recognizable actor name."""
    username = _clean(getattr(actor, "username", None))
    if username:
        return username

    name = _clean(getattr(actor, "name", None))
    family = _clean(getattr(actor, "family", None))
    full_name = " ".join(part for part in (name, family) if part)

    return full_name or "Someone"


def messenger_actor_name(actor) -> str:
    """Prefer display name for Messenger without exposing message content."""
    name = _clean(getattr(actor, "name", None))
    family = _clean(getattr(actor, "family", None))
    full_name = " ".join(part for part in (name, family) if part)

    if full_name:
        return full_name

    return actor_name(actor)


def content_name(obj) -> str:
    """Return a clear user-facing name for supported content."""
    if not obj:
        return "post"

    meta = getattr(obj, "_meta", None)
    model_name = _clean(getattr(meta, "model_name", None)).lower()

    labels = {
        "moment": "Moment",
        "prayer": "Prayer",
        "testimony": "Testimony",
        "journey": "Journey",
        "journeyentry": "Journey",
    }

    return labels.get(model_name, "post")


def reaction_name(reaction_type: Any) -> str:
    code = _clean(reaction_type).lower()
    return REACTION_LABELS.get(code, "Reaction")


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


# -------------------------------------------------------------------------
# In-app notification copy
# -------------------------------------------------------------------------

def build_comment_message(notification_type: str, actor, target_obj) -> str:
    actor_label = actor_name(actor)
    content_label = content_name(target_obj)

    if notification_type == "new_reply":
        return f"{actor_label} replied to your comment on a {content_label}."

    if notification_type == "new_reply_post_owner":
        return f"{actor_label} replied to a comment on your {content_label}."

    return f"{actor_label} commented on your {content_label}."


def build_reaction_message(
    actor,
    target_obj,
    reaction_type: str,
    has_private_message: bool,
) -> str:
    actor_label = actor_name(actor)
    content_label = content_name(target_obj)
    reaction_label = reaction_name(reaction_type)

    if has_private_message:
        article = _article_for(reaction_label)
        return (
            f"{actor_label} sent you a private message with {article} "
            f"{reaction_label} reaction on your {content_label}."
        )

    if reaction_label == "Reaction":
        return f"{actor_label} reacted to your {content_label}."

    return f"{actor_label} reacted with {reaction_label} to your {content_label}."


def build_friendship_message(notification_type: str, actor) -> str:
    actor_label = actor_name(actor)

    messages = {
        "friend_request_received": f"{actor_label} sent you a friend request.",
        "friend_request_accepted": f"{actor_label} accepted your friend request.",
        "friend_request_declined": f"{actor_label} declined your friend request.",
        "friend_request_cancelled": f"{actor_label} cancelled their friend request.",
        "friendship_deleted": f"{actor_label} removed you from their friends.",
    }

    return messages.get(notification_type, f"Friendship update from {actor_label}.")


def build_fellowship_message(
    notification_type: str,
    actor,
    relation: str,
) -> str:
    actor_label = actor_name(actor)
    relation_label = _clean(relation) or "fellowship"

    messages = {
        "fellowship_request_received": (
            f"{actor_label} sent you a LITCovenant request as {relation_label}."
        ),
        "fellowship_request_accepted": (
            f"{actor_label} accepted your LITCovenant request as {relation_label}."
        ),
        "fellowship_request_confirmed": (
            f"Your LITCovenant with {actor_label} as {relation_label} is now confirmed."
        ),
        "fellowship_request_declined": (
            f"{actor_label} declined your LITCovenant request as {relation_label}."
        ),
        "fellowship_decline_notice": (
            f"Your response to {actor_label}'s LITCovenant request was recorded."
        ),
        "fellowship_cancelled": (
            f"Your LITCovenant with {actor_label} as {relation_label} was cancelled."
        ),
    }

    return messages.get(notification_type, f"LITCovenant update with {actor_label}.")


def build_journey_message(actor) -> str:
    return f"{actor_name(actor)} added a new entry to their Journey."


def build_moment_message(actor, kind: str) -> str:
    actor_label = actor_name(actor)

    if _clean(kind).lower() == "video":
        return f"{actor_label} shared a new video Moment."

    return f"{actor_label} shared a new Moment."


def build_prayer_message(actor, event: str) -> str:
    actor_label = actor_name(actor)

    if event == "new_video":
        return f"{actor_label} shared a new Prayer request with a video."

    if event == "new_image":
        return f"{actor_label} shared a new Prayer request."

    if event == "answered":
        return f"{actor_label} shared that a Prayer was answered."

    if event == "follow_up":
        return f"{actor_label} shared a follow-up on a Prayer request."

    return f"{actor_label} shared a Prayer update."


def build_testimony_message(actor, kind: str) -> str:
    actor_label = actor_name(actor)
    normalized_kind = _clean(kind).lower()

    if normalized_kind == "audio":
        return f"{actor_label} shared a new audio Testimony."

    if normalized_kind == "video":
        return f"{actor_label} shared a new video Testimony."

    if normalized_kind == "written":
        return f"{actor_label} shared a new written Testimony."

    return f"{actor_label} shared a new Testimony."


def build_messenger_message(
    actor,
    *,
    is_group: bool,
    group_name: str | None,
) -> str:
    sender = messenger_actor_name(actor)

    if is_group and _clean(group_name):
        return f"From {sender} in {_clean(group_name)}"

    return f"From {sender}"


# -------------------------------------------------------------------------
# Push presentation
# -------------------------------------------------------------------------

def push_title_for_notification(
    notification_type: str,
    extra_payload: Mapping[str, Any] | None = None,
) -> str:
    payload = _payload(extra_payload)

    if notification_type in {"new_message_direct", "new_message_group"}:
        kind = _clean(payload.get("message_kind")).lower()
        kind_labels = {
            "voice": "voice message",
            "video": "video message",
            "image": "image message",
            "file": "file",
            "text": "message",
        }

        message_label = kind_labels.get(kind, "message")

        if notification_type == "new_message_group":
            return f"New group {message_label}"

        return f"New {message_label}"

    if notification_type.startswith("new_reaction"):
        if _truthy(payload.get("has_message")):
            return "Private reaction message"

        label = reaction_name(payload.get("reaction_type"))

        if label != "Reaction":
            return f"{label} reaction"

        type_suffix = notification_type.removeprefix("new_reaction_")
        inferred_label = reaction_name(type_suffix)

        if inferred_label != "Reaction":
            return f"{inferred_label} reaction"

        return "New reaction"

    return STATIC_PUSH_TITLES.get(notification_type, "TownLIT Notification")


def push_body_for_notification(notification_type: str, message: str) -> str:
    special_body = TESTIMONY_STATUS_PUSH_BODIES.get(notification_type)
    if special_body:
        return special_body

    clean_message = _clean(message)

    if len(clean_message) > 180:
        return clean_message[:177] + "..."

    return clean_message


def email_subject_for_notification(notification_type: str) -> str:
    if notification_type == "testimony_video_rejected":
        return "Your TownLIT video Testimony was not accepted"

    if notification_type == "testimony_video_needs_review":
        return "Your TownLIT video Testimony is being reviewed"

    if notification_type == "testimony_video_approved":
        return "Your TownLIT video Testimony was approved"

    title = STATIC_PUSH_TITLES.get(notification_type)

    if title:
        return f"TownLIT: {title}"

    return "New Notification from TownLIT"