import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.posts.models import Reaction
from apps.notifications.services import create_and_dispatch_notification

logger = logging.getLogger(__name__)


# =====================================================
# 🔸 Reaction → Message Mapping
# =====================================================
def _reaction_message(username: str, rtype: str) -> tuple[str, str]:
    """Return user-facing message + notification type."""
    mapping = {
        "like":         (f"{username} liked your post.", "new_reaction_like"),
        "bless":        (f"{username} sent you a blessing.", "new_reaction_bless"),
        "gratitude":    (f"{username} expressed gratitude.", "new_reaction_gratitude"),
        "amen":         (f"{username} said Amen to your post.", "new_reaction_amen"),
        "encouragement":(f"{username} encouraged your post.", "new_reaction_encouragement"),
        "empathy":      (f"{username} expressed empathy.", "new_reaction_empathy"),
        "faithfire":    (f"{username} was inspired by your faith.", "new_reaction_faithfire"),
        "support":      (f"{username} stands with you in support.", "new_reaction_support"),
    }
    return mapping.get(rtype, (f"{username} reacted to your post.", "new_reaction"))


# =====================================================
# 🔸 Owner Resolver (generic)
# =====================================================
def _resolve_owner(obj):
    """Attempt to find the logical owner (user) of the target content."""
    if not obj:
        return None

    # Common ownership fields
    for attr in ("user", "owner", "author", "created_by", "name", "member_user", "org_owner_user"):
        val = getattr(obj, attr, None)
        if val is not None and hasattr(val, "id"):
            return val

    # Fallback: nested objects
    try:
        if hasattr(obj, "content_object"):
            inner = obj.content_object
            for attr in ("user", "owner", "org_owner_user"):
                val = getattr(inner, attr, None)
                if val is not None and hasattr(val, "id"):
                    return val
    except Exception as e:
        logger.debug(f"[Notif] _resolve_owner fallback failed for {obj}: {e}")

    return None


# =====================================================
# 🔸 Main Reaction Signal
# =====================================================
@receiver(post_save, sender=Reaction, dispatch_uid="notifications.reaction.create_v4")
def on_reaction_created(sender, instance: Reaction, created, **kwargs):
    """Send notification only if the reaction has a message."""
    if not created:
        return

    actor = getattr(instance, "name", None)
    if not actor:
        logger.debug("[Notif] Reaction skipped: missing actor.")
        return

    # ✅ skip if no message (text is None or blank after decryption)
    msg_text = (instance.message or "").strip()
    if not msg_text:
        logger.debug(f"[Notif] Reaction skipped (no message) from {actor.username}")
        return

    content_object = getattr(instance, "content_object", None)
    to_user = _resolve_owner(content_object)

    # Skip invalid or self-target
    if not to_user or to_user.id == actor.id:
        logger.debug(f"[Notif] Reaction skipped: invalid/self target for {actor.username}")
        return

    # Map to readable text + notif type
    msg_template, notif_type = _reaction_message(actor.username, getattr(instance, "reaction_type", ""))

    # Combine both: custom message first, fallback template for clarity
    full_msg = f"{msg_template}\n\n💬 “{msg_text}”" if msg_text else msg_template

    # ✅ Create + dispatch notification
    try:
        create_and_dispatch_notification(
            recipient=to_user,
            actor=actor,
            notif_type=notif_type,
            message=full_msg,
            target_obj=content_object,
            action_obj=instance,  # provides deep-link
        )
        logger.debug(f"[Notif] Reaction → {to_user.username} ({notif_type}) by {actor.username}")
    except Exception as e:
        logger.exception(f"[Notif] Failed to dispatch reaction notification: {e}")
