# apps/profiles/selectors/common_suggestions.py

from django.db.models import Q
import random

from django.contrib.auth import get_user_model

from apps.profiles.models import Friendship

CustomUser = get_user_model()


# Suggest friends for the Requests tab with active/pending exclusion ------------------------------
def suggest_friends_for_requests_tab(
    user,
    limit=5,
    extra_exclude_ids=None,
):
    """
    Suggest users for the Requests & Invites tab.

    Policy:
    - Exclude self.
    - Exclude accepted/pending relationships.
    - Exclude Boundary/visibility IDs passed by the ViewSet.
    - Exclude friend-of-friend candidates.
      Those belong to friends-suggestions, not requests-suggestions.
    - Do NOT permanently exclude declined/deleted relationships.
    """

    if not user.is_active or user.is_deleted:
        return []

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5

    limit = max(1, min(limit, 20))

    exclude_ids = {user.id}
    exclude_ids.update(set(extra_exclude_ids or []))

    # 1) Exclude active relationships: accepted + pending.
    active_friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status__in=[
            "accepted",
            "pending",
        ],
    ).values_list(
        "from_user_id",
        "to_user_id",
    )

    friend_ids = set()

    for from_user_id, to_user_id in active_friendships:
        other_user_id = to_user_id if from_user_id == user.id else from_user_id
        exclude_ids.add(other_user_id)

        # Keep only accepted friends for friend-of-friend exclusion below.
        # We cannot know status from values_list above, so accepted friends
        # are collected in a dedicated query below.
    
    # 2) Current accepted friends.
    accepted_friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status="accepted",
    ).values_list(
        "from_user_id",
        "to_user_id",
    )

    for from_user_id, to_user_id in accepted_friendships:
        if from_user_id == user.id:
            friend_ids.add(to_user_id)
        else:
            friend_ids.add(from_user_id)

    # 3) Exclude friend-of-friend candidates from Requests tab.
    # These should appear in friends-suggestions instead.
    if friend_ids:
        friend_of_friend_edges = Friendship.objects.filter(
            Q(from_user_id__in=friend_ids) | Q(to_user_id__in=friend_ids),
            status="accepted",
        ).exclude(
            Q(from_user_id=user.id) | Q(to_user_id=user.id)
        ).values_list(
            "from_user_id",
            "to_user_id",
        )

        friend_of_friend_ids = set()

        for from_user_id, to_user_id in friend_of_friend_edges:
            if from_user_id in friend_ids:
                friend_of_friend_ids.add(to_user_id)

            if to_user_id in friend_ids:
                friend_of_friend_ids.add(from_user_id)

        exclude_ids.update(friend_of_friend_ids)

    eligible_suggestions = list(
        CustomUser.objects
        .filter(
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )
        .exclude(id__in=exclude_ids)
        .select_related(
            "label",
            "member_profile",
        )
        .distinct()
    )

    random.shuffle(eligible_suggestions)

    return eligible_suggestions[:limit]