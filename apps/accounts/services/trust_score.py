# apps/accounts/services/trust_score.py

# apps/accounts/services/trust_score.py

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.contrib.auth import get_user_model

from apps.accounts.models.trust import UserTrustScore
from apps.accounts.constants import trust_weights as W

from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.testimony import Testimony

from apps.profiles.models import Member, GuestUser, Friendship
from apps.profiles.constants import ACCEPTED

from apps.sanctuary.models import SanctuaryRequest
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


def _has_custom_avatar(user):
    """
    Return True if user has a non-default avatar.
    """
    img = getattr(user, "image_name", None)
    if not img:
        return False

    raw_value = str(getattr(img, "name", None) or str(img) or "").strip()

    default_url = getattr(settings, "DEFAULT_USER_AVATAR_URL", "") or ""
    default_path = "/static/defaults/default-avatar.png"

    if not raw_value:
        return False

    if raw_value == default_url:
        return False

    if raw_value.endswith(default_path):
        return False

    return True


def _get_user_profile_targets(user):
    """
    Return polymorphic owner targets for this user.
    Supports Member and GuestUser profiles.
    """
    targets = []

    profile_models = [Member, GuestUser]

    for profile_model in profile_models:
        profile_id = profile_model.objects.filter(user_id=user.id).values_list("id", flat=True).first()
        if profile_id:
            profile_ct = ContentType.objects.get_for_model(profile_model)
            targets.append((profile_ct, profile_id))

    return targets


def _count_user_moments(user):
    """
    Count moments owned by this user's profiles.
    """
    targets = _get_user_profile_targets(user)
    if not targets:
        return 0

    q = Q()
    for ct, obj_id in targets:
        q |= Q(content_type=ct, object_id=obj_id)

    return Moment.objects.filter(q).count()


def _count_user_prayers(user):
    """
    Count prayers owned by this user's profiles.
    """
    targets = _get_user_profile_targets(user)
    if not targets:
        return 0

    q = Q()
    for ct, obj_id in targets:
        q |= Q(content_type=ct, object_id=obj_id)

    return Prayer.objects.filter(q).count()


def _count_user_testimonies(user):
    """
    Count testimonies owned by this user's profiles.
    """
    targets = _get_user_profile_targets(user)
    if not targets:
        return 0

    q = Q()
    for ct, obj_id in targets:
        q |= Q(content_type=ct, object_id=obj_id)

    return Testimony.objects.filter(q).count()


def _count_user_friendships(user):
    """
    Count accepted active friendships once per real relationship.

    Because the system stores symmetric accepted rows,
    we only count rows initiated by this user.
    """
    return Friendship.objects.filter(
        from_user=user,
        is_active=True,
        status=ACCEPTED,
    ).count()


def _count_account_reports(user):
    """
    Count sanctuary requests targeting this account.
    """
    user_ct = ContentType.objects.get_for_model(User)

    return SanctuaryRequest.objects.filter(
        content_type=user_ct,
        object_id=user.id,
    ).count()


def calculate_trust_score(user):
    """
    Calculate trust score for verification eligibility.
    """
    score = 0

    # ----- profile signals -----
    # if user.is_active:
    #     score += W.EMAIL_VERIFIED

    if user.mobile_number:
        score += W.PHONE_VERIFIED

    if user.name and user.family:
        score += W.NAME_COMPLETED

    if user.birthday:
        score += W.BIRTHDAY_COMPLETED

    if user.gender:
        score += W.GENDER_COMPLETED

    if getattr(user, "country", None):
        score += W.COUNTRY_COMPLETED

    if getattr(user, "primary_language", None):
        score += W.PRIMARY_LANGUAGE_COMPLETED

    if _has_custom_avatar(user):
        score += W.AVATAR_CHANGED

    # ----- activity signals -----
    moment_count = _count_user_moments(user)
    moment_score = min(moment_count * W.MOMENT_CREATED, W.MAX_MOMENT_SCORE)
    score += moment_score

    prayer_count = _count_user_prayers(user)
    prayer_score = min(prayer_count * W.PRAYER_CREATED, W.MAX_PRAYER_SCORE)
    score += prayer_score

    testimony_count = _count_user_testimonies(user)
    testimony_score = min(testimony_count * W.TESTIMONY_CREATED, W.MAX_TESTIMONY_SCORE)
    score += testimony_score

    # ----- social signals -----
    friendship_count = _count_user_friendships(user)
    friendship_score = min(friendship_count * W.FRIEND_CREATED, W.MAX_FRIEND_SCORE)
    score += friendship_score

    # ----- negative signals -----
    report_count = _count_account_reports(user)
    report_penalty = max(
        report_count * W.ACCOUNT_REPORT_PENALTY,
        W.MAX_REPORT_PENALTY,
    )
    score += report_penalty

    return max(score, 0)


def update_user_trust_score(user):
    """
    Recalculate and persist trust score.
    """
    score = calculate_trust_score(user)

    trust, _ = UserTrustScore.objects.get_or_create(user=user)
    trust.score = score
    trust.eligible_for_verification = score >= W.VERIFICATION_THRESHOLD
    trust.save(update_fields=["score", "eligible_for_verification", "last_calculated"])

    return trust