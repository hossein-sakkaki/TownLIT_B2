from django.db.models import Q
import random
from datetime import timedelta
from django.utils import timezone

from apps.profiles.models import Friendship
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Suggest friends for the Friends tab (based on mutual friends and graceful timeouts) -------------------------
def suggest_friends_for_friends_tab(user, limit=5):
    """Suggest friends for the Friends tab."""

    if not user.is_active or user.is_deleted:
        return []
    
    exclude_users = [user.id]

    # Get users to exclude based on friendship statuses
    excluded_friendships = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status__in=['accepted', 'pending', 'declined', 'deleted']
    )
    exclude_ids = set(friendship.from_user.id if friendship.to_user == user else friendship.to_user.id for friendship in excluded_friendships)
    exclude_users.extend(exclude_ids)

    # Get mutual friends
    friends = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status='accepted'
    )
    friend_ids = set(friend.from_user.id if friend.to_user == user else friend.to_user.id for friend in friends)

    mutual_friendships = Friendship.objects.filter(
        Q(from_user__in=friend_ids) | Q(to_user__in=friend_ids),
        status='accepted'
    ).exclude(
        Q(from_user=user) | Q(to_user=user)
    )
    mutual_ids = set(friend.from_user.id if friend.to_user in friend_ids else friend.to_user.id for friend in mutual_friendships)

    # Get eligible suggestions
    eligible_suggestions = (
        CustomUser.objects
        .filter(
            Q(id__in=mutual_ids),
            is_active=True,
            is_deleted=False
        )
        .exclude(id__in=exclude_users)
        .distinct()
    )

    # Convert QuerySet to list and shuffle
    eligible_suggestions_list = list(eligible_suggestions)
    random.shuffle(eligible_suggestions_list)

    # Select 'limit' number of users
    suggestions = eligible_suggestions_list[:limit]

    return suggestions




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

    # فیلتر پیشنهادی بر اساس کشور/زبان (در صورت نیاز می‌تونی این بخش رو اضافه کنی)
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
