# apps/notifications/signals/reaction_signals.py

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.posts.models.reaction import Reaction
from apps.notifications.services.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


# ----------------------------------------------------
# reaction_type -> (message suffix, notif_type)
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
    """Return (full message, notif_type) with safe fallback."""
    msg, ntype = REACTION_MAP.get(reaction_code, ("reacted to your post", "new_reaction"))
    return f"{username} {msg}", ntype


# ----------------------------------------------------
# Resolve "owner user" from a target object (generic)
# ----------------------------------------------------
def _resolve_owner(obj):
    if not obj:
        return None

    # common ownership patterns
    for attr in ("user", "owner", "author", "created_by", "name", "member_user", "org_owner_user"):
        val = getattr(obj, attr, None)
        if val is not None and hasattr(val, "id"):
            return val

    # fallback: nested content_object
    try:
        inner = getattr(obj, "content_object", None)
        if inner:
            for attr in ("user", "owner", "org_owner_user"):
                val = getattr(inner, attr, None)
                if val is not None and hasattr(val, "id"):
                    return val
    except Exception:
        pass

    return None


# ----------------------------------------------------
# Main signal: Reaction created
# ----------------------------------------------------
@receiver(post_save, sender=Reaction, dispatch_uid="notif.reaction.create_v6")
def on_reaction_created(sender, instance: Reaction, created, **kwargs):
    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        logger.debug("[Notif] Reaction skipped: no actor.")
        return

    # optional reaction message
    msg_text = (instance.message or "").strip()
    if instance.message is None:
        msg_text = ""  # keep consistent

    target = getattr(instance, "content_object", None)
    to_user = _resolve_owner(target)

    # skip invalid/self
    if not to_user or to_user.id == actor.id:
        logger.debug("[Notif] Reaction skipped: invalid/self target.")
        return

    # message + type
    base_msg, notif_type = _reaction_template(
        actor.username,
        getattr(instance, "reaction_type", "") or ""
    )
    full_msg = f'{base_msg}: “{msg_text}”' if msg_text else base_msg

    # payload used by smart deep-link + clients
    payload = {
        # ✅ enables focus=reaction-<id>
        "reaction_id": instance.id,

        # extra metadata (optional)
        "reaction_type": getattr(instance, "reaction_type", None),
        "has_message": bool(msg_text),
        "target_type": target._meta.label_lower if target and hasattr(target, "_meta") else None,
        "target_id": getattr(target, "pk", None),
    }

    try:
        create_and_dispatch_notification(
            recipient=to_user,
            actor=actor,
            notif_type=notif_type,
            message=full_msg,
            target_obj=target,
            action_obj=instance,     # lets service resolve root via content_type/object_id if present
            extra_payload=payload,
        )
        logger.debug("[Notif] Reaction delivered: to=%s type=%s", to_user.id, notif_type)

    except Exception as e:
        logger.exception("[Notif] Reaction dispatch failed: %s", e)
