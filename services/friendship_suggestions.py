from django.db.models import Q
import random
from datetime import timedelta
from django.utils import timezone

from apps.profiles.models import Friendship
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




# Suggest friends for the Friends tab (based on mutual friends and graceful timeouts) -------------------------
# def suggest_friends_for_friends_tab(user, limit=5):
#     now = timezone.now()
#     exclude_users = {user.id}

#     # روابط فعال (pending و accepted)
#     active_friendships = Friendship.objects.filter(
#         Q(from_user=user) | Q(to_user=user),
#         status__in=['pending', 'accepted']
#     )

#     # روابط لغو شده‌ی اخیر (نه همه)
#     delayed_excludes = Friendship.objects.filter(
#         Q(from_user=user) | Q(to_user=user),
#         Q(status='declined', updated_at__gt=now - timedelta(weeks=4)) |
#         Q(status='cancelled', updated_at__gt=now - timedelta(weeks=2)) |
#         Q(status='deleted', updated_at__gt=now - timedelta(weeks=2))
#     )

#     def get_other_id(friendship):
#         return friendship.from_user.id if friendship.to_user == user else friendship.to_user.id

#     exclude_users |= {get_other_id(f) for f in active_friendships}
#     exclude_users |= {get_other_id(f) for f in delayed_excludes}

#     # دوستان فعلی کاربر
#     accepted_friendships = Friendship.objects.filter(
#         Q(from_user=user) | Q(to_user=user),
#         status='accepted'
#     )
#     friend_ids = {get_other_id(f) for f in accepted_friendships}

#     # روابط accepted بین دوستان کاربر با سایر کاربران
#     mutual_friendships = Friendship.objects.filter(
#         Q(from_user__in=friend_ids) | Q(to_user__in=friend_ids),
#         status='accepted'
#     ).exclude(
#         Q(from_user=user) | Q(to_user=user)
#     )

#     # استخراج ID طرف مقابل
#     mutual_ids = set()
#     for friendship in mutual_friendships:
#         if friendship.from_user.id in friend_ids and friendship.to_user.id not in exclude_users:
#             mutual_ids.add(friendship.to_user.id)
#         elif friendship.to_user.id in friend_ids and friendship.from_user.id not in exclude_users:
#             mutual_ids.add(friendship.from_user.id)

#     # پیشنهادات نهایی
#     eligible_suggestions = CustomUser.objects.filter(id__in=mutual_ids).exclude(id__in=exclude_users).distinct()

#     eligible_suggestions_list = list(eligible_suggestions)
#     random.shuffle(eligible_suggestions_list)

#     return eligible_suggestions_list[:limit]
def suggest_friends_for_friends_tab(user, limit=5):
    """Suggest friends for the Friends tab."""
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
    eligible_suggestions = CustomUser.objects.filter(
        # Q(id__in=mutual_ids) |
        # Q(member_profile__denomination_type=user.member.denomination_type)
        
        Q(id__in=mutual_ids)
    ).exclude(id__in=exclude_users).distinct()

    # Convert QuerySet to list and shuffle
    eligible_suggestions_list = list(eligible_suggestions)
    random.shuffle(eligible_suggestions_list)

    # Select 'limit' number of users
    suggestions = eligible_suggestions_list[:limit]

    return suggestions




# Suggest friends for the Requests tab with delay policy for declined/cancelled/deleted ------------------------------
# def suggest_friends_for_requests_tab(user, limit=5):
#     exclude_users = [user.id]

#     now = timezone.now()

#     # روابط فعال (دوستی یا درخواست جاری)
#     active_friendships = Friendship.objects.filter(
#         Q(from_user=user) | Q(to_user=user),
#         status__in=['pending', 'accepted']
#     )

#     # روابط اخیراً declined/cancelled/deleted که هنوز زمان بازگشت‌شان نرسیده
#     delayed_friendships = Friendship.objects.filter(
#         Q(from_user=user) | Q(to_user=user),
#         Q(status='declined', updated_at__gt=now - timedelta(weeks=3)) |
#         Q(status='cancelled', updated_at__gt=now - timedelta(weeks=2)) |
#         Q(status='deleted', updated_at__gt=now - timedelta(weeks=2))
#     )

#     # استخراج ID کاربران طرف مقابل در روابط
#     def get_other_user_id(friendship):
#         return friendship.from_user.id if friendship.to_user == user else friendship.to_user.id

#     exclude_ids = set(get_other_user_id(f) for f in active_friendships) | \
#                   set(get_other_user_id(f) for f in delayed_friendships)

#     exclude_users.extend(exclude_ids)

#     # پیشنهاد کاربران واجد شرایط
#     eligible_suggestions = CustomUser.objects.exclude(id__in=exclude_users).distinct()

#     eligible_suggestions_list = list(eligible_suggestions)
#     random.shuffle(eligible_suggestions_list)

#     return eligible_suggestions_list[:limit]


def suggest_friends_for_requests_tab(user, limit=5):
    """Suggest friends for the Requests tab (excluding only active/pending relations)."""
    exclude_users = [user.id]

    # فقط روابط active (pending یا accepted) را حذف کن
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
    eligible_suggestions = CustomUser.objects.exclude(id__in=exclude_users).distinct()

    eligible_suggestions_list = list(eligible_suggestions)
    random.shuffle(eligible_suggestions_list)

    return eligible_suggestions_list[:limit]
