# apps/conversation/services/realtime_access.py

from apps.conversation.models import Dialogue


def get_dialogue_for_user(dialogue_slug, user):
    """
    Load one dialogue only if the user is a participant.
    """
    if not dialogue_slug or not user or not getattr(user, "is_authenticated", False):
        return None

    return Dialogue.objects.filter(
        slug=dialogue_slug,
        participants=user,
    ).first()