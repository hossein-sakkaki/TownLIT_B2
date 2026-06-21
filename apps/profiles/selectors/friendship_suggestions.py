# apps/profiles/selectors/friendship_suggestions.py

from django.db.models import Q
import random

from django.contrib.auth import get_user_model

from apps.profiles.models import Friendship

CustomUser = get_user_model()


# Suggest friends for the Friends tab (based on mutual friends) -------------------------
def suggest_friends_for_friends_tab(
    user,
    limit=5,
    extra_exclude_ids=None,
):
    """
    Suggest users for the Friends tab.

    Policy:
    - Only friend-of-friend suggestions.
    - Must have at least one accepted mutual friend.
    - Exclude self.
    - Exclude current accepted friendships.
    - Exclude current pending requests in either direction.
    - Do NOT permanently exclude declined/deleted relationships.
      Those users may be suggested again later if they are otherwise eligible.
    - Exclude boundary/visibility IDs passed by the ViewSet.
    """

    if not user.is_active or user.is_deleted:
        return []

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 5

    limit = max(1, min(limit, 20))

    extra_exclude_ids = set(extra_exclude_ids or [])

    exclude_ids = {user.id}
    exclude_ids.update(extra_exclude_ids)

    # Important:
    # Only accepted/pending should block suggestions.
    # declined/deleted should not permanently hide users from suggestions.
    blocking_friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status__in=[
            "accepted",
            "pending",
        ],
    ).values_list(
        "from_user_id",
        "to_user_id",
    )

    for from_user_id, to_user_id in blocking_friendships:
        if from_user_id == user.id:
            exclude_ids.add(to_user_id)
        else:
            exclude_ids.add(from_user_id)

    # Current accepted friends of the viewer.
    accepted_friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status="accepted",
    ).values_list(
        "from_user_id",
        "to_user_id",
    )

    friend_ids = set()

    for from_user_id, to_user_id in accepted_friendships:
        if from_user_id == user.id:
            friend_ids.add(to_user_id)
        else:
            friend_ids.add(from_user_id)

    if not friend_ids:
        return []

    # Friends of viewer's friends.
    friend_of_friend_edges = Friendship.objects.filter(
        Q(from_user_id__in=friend_ids) | Q(to_user_id__in=friend_ids),
        status="accepted",
    ).exclude(
        Q(from_user_id=user.id) | Q(to_user_id=user.id)
    ).values_list(
        "from_user_id",
        "to_user_id",
    )

    candidate_ids = set()

    for from_user_id, to_user_id in friend_of_friend_edges:
        if from_user_id in friend_ids:
            candidate_ids.add(to_user_id)

        if to_user_id in friend_ids:
            candidate_ids.add(from_user_id)

    candidate_ids.difference_update(exclude_ids)

    if not candidate_ids:
        return []

    suggestions = list(
        CustomUser.objects
        .filter(
            id__in=candidate_ids,
            is_active=True,
            is_deleted=False,
            is_suspended=False,
        )
        .select_related(
            "label",
            "member_profile",
        )
        .distinct()
    )

    random.shuffle(suggestions)

    return suggestions[:limit]