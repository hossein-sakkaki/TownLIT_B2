# apps/notifications/signals/reaction_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.posts.models.reaction import Reaction
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


# ----------------------------------------------------
# 🔹 Map: reaction_type → (user-facing message, notif_type)
# ----------------------------------------------------
REACTION_MAP = {
    "like":          ("liked your post",              "new_reaction_like"),
    "bless":         ("sent you a blessing",          "new_reaction_bless"),
    "gratitude":     ("expressed gratitude",          "new_reaction_gratitude"),
    "amen":          ("said Amen to your post",       "new_reaction_amen"),
    "encouragement": ("encouraged your post",         "new_reaction_encouragement"),
    "empathy":       ("expressed empathy",            "new_reaction_empathy"),
    "faithfire":     ("was inspired by your faith",   "new_reaction_faithfire"),
    "support":       ("stands with you in support",   "new_reaction_support"),
}


def _reaction_template(username: str, reaction_code: str):
    """Returns (message, notif_type) with safe fallback."""
    if reaction_code in REACTION_MAP:
        msg, ntype = REACTION_MAP[reaction_code]
        return f"{username} {msg}", ntype

    return f"{username} reacted to your post", "new_reaction"


# ----------------------------------------------------
# 🔹 Resolve content owner
# ----------------------------------------------------
def _resolve_owner(obj):
    if not obj:
        return None

    # direct ownership patterns
    for attr in ("user", "owner", "author", "created_by", "name", "member_user", "org_owner_user"):
        val = getattr(obj, attr, None)
        if hasattr(val, "id"):
            return val

    # fallback generic content_object
    content = getattr(obj, "content_object", None)
    if content:
        for attr in ("user", "owner", "org_owner_user"):
            val = getattr(content, attr, None)
            if hasattr(val, "id"):
                return val

    return None


# ----------------------------------------------------
# 🔹 Main Reaction Notification Signal
# ----------------------------------------------------
@receiver(post_save, sender=Reaction, dispatch_uid="notif.reaction.create_v5")
def on_reaction_created(sender, instance: Reaction, created, **kwargs):
    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        logger.debug("[Notif] Reaction skipped — no actor on instance.")
        return

    # Reaction text (user-entered message) — decrypt already done in model
    msg_text = (instance.message or "").strip()

    # If user did not write a message → OK (still send the emoji reaction)
    # But if msg exists and is only whitespace → ignore
    # (You already implemented this logic properly; keeping it clean)
    if instance.message is None:
        msg_text = ""

    target = getattr(instance, "content_object", None)
    to_user = _resolve_owner(target)

    if not to_user or to_user.id == actor.id:
        logger.debug(f"[Notif] Reaction skipped (invalid/self target) → {actor.username}")
        return

    # Template reaction message
    base_msg, notif_type = _reaction_template(actor.username, getattr(instance, "reaction_type", ""))

    # Combine with optional custom message
    full_msg = base_msg
    if msg_text:
        full_msg = f"{base_msg}: “{msg_text}”"

    # unified payload (useful for push, WS, analytics)
    payload = {
        "reaction_id": instance.id,
        "reaction_type": instance.reaction_type,
        "has_message": bool(msg_text),
        "target_type": target.__class__.__name__ if target else None,
        "target_id": getattr(target, "id", None),
    }

    # Create + dispatch
    try:
        create_and_dispatch_notification(
            recipient=to_user,
            actor=actor,
            notif_type=notif_type,
            message=full_msg,
            target_obj=target,
            action_obj=instance,     # enables deep-link
            extra_payload=payload,   # WebPush + WS need this
        )

        logger.debug(
            f"[Notif] Reaction delivered → {to_user.username} | type={notif_type} | actor={actor.username}"
        )

    except Exception as e:
        logger.exception(f"[Notif] Failed to dispatch reaction notification: {e}")
