# apps/profiles/selectors/common_suggestions.py

from django.db.models import Q
import random

from apps.profiles.models import Friendship
from django.contrib.auth import get_user_model
CustomUser = get_user_model()


# Suggest friends for the Requests tab with delay policy for declined/cancelled/deleted ------------------------------
def suggest_friends_for_requests_tab(user, limit=5):
    """Suggest friends for the Requests tab (excluding only active/pending relations)."""
    if not user.is_active or user.is_deleted:
        return []
    
    exclude_users = [user.id]
    active_statuses = ['pending', 'accepted']

    friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status__in=active_statuses
    )

    exclude_ids = set(
        friendship.from_user.id if friendship.to_user == user else friendship.to_user.id
        for friendship in friendships
    )
    exclude_users.extend(exclude_ids)

    eligible_suggestions = (
        CustomUser.objects
        .filter(
            is_active=True,
            is_deleted=False
        )
        .exclude(id__in=exclude_users)
        .distinct()
    )

    eligible_suggestions_list = list(eligible_suggestions)
    random.shuffle(eligible_suggestions_list)

    return eligible_suggestions_list[:limit]
