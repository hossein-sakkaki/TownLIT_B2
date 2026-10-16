# apps/conversation/services/realtime_access.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

from apps.conversation.models import Dialogue
from apps.conversation.policies import ConversationAccessPolicy


def get_dialogue_for_user(dialogue_slug, user):
    """Load one dialogue through the context-aware Conversation access policy."""
    if not dialogue_slug or not user or not getattr(user, "is_authenticated", False):
        return None

    dialogue = (
        Dialogue.objects
        .select_related(
            "organization_context__organization",
            "organization_context__participant_user",
        )
        .filter(slug=dialogue_slug)
        .first()
    )
    if dialogue is None:
        return None

    decision = ConversationAccessPolicy.can_view(
        dialogue=dialogue,
        user=user,
    )
    return dialogue if decision.allowed else None
