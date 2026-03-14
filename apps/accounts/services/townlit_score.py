# apps/accounts/services/townlit_score.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from apps.accounts.constants import townlit_weights as W
from apps.posts.models.moment import Moment
from apps.posts.models.pray import Prayer
from apps.posts.models.testimony import Testimony
from apps.profiles.constants import ACCEPTED
from apps.profiles.models import Friendship, Member, MemberSpiritualGifts
from apps.sanctuary.models import SanctuaryRequest

User = get_user_model()


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _member_ct():
    return ContentType.objects.get_for_model(Member)


def _count_member_moments(member: Member) -> int:
    return Moment.objects.filter(
        content_type=_member_ct(),
        object_id=member.id,
        is_active=True,
        is_hidden=False,
    ).count()


def _count_member_prayers(member: Member) -> int:
    return Prayer.objects.filter(
        content_type=_member_ct(),
        object_id=member.id,
        is_active=True,
        is_hidden=False,
    ).count()


def _count_member_testimonies(member: Member) -> int:
    return Testimony.objects.filter(
        content_type=_member_ct(),
        object_id=member.id,
        is_active=True,
        is_hidden=False,
    ).count()


def _count_member_friendships(member: Member) -> int:
    return Friendship.objects.filter(
        from_user=member.user,
        is_active=True,
        status=ACCEPTED,
    ).count()


def _count_member_organization_memberships(member: Member) -> int:
    return member.organization_memberships.count()


def _count_member_service_types(member: Member) -> int:
    return member.service_types.count()


def _has_completed_spiritual_gifts(member: Member) -> bool:
    """
    A member is considered spiritually-gifts-complete when:
    - a MemberSpiritualGifts row exists
    - at least one gift is selected
    - survey_results is not empty
    """
    row = (
        MemberSpiritualGifts.objects
        .filter(member=member)
        .prefetch_related("gifts")
        .first()
    )

    if not row:
        return False

    if not row.gifts.exists():
        return False

    if not row.survey_results:
        return False

    return True


def _count_account_reports(user) -> int:
    user_ct = ContentType.objects.get_for_model(User)

    return SanctuaryRequest.objects.filter(
        content_type=user_ct,
        object_id=user.id,
    ).count()


def calculate_member_townlit_score(member: Member) -> int:
    """
    Score used for INITIAL TownLIT gold unlock.

    IMPORTANT:
    If score later falls below threshold, gold is NOT revoked automatically.
    """
    score = 0

    # ----- profile maturity signals -----
    if _normalize_text(member.biography):
        score += W.BIOGRAPHY_COMPLETED

    if _normalize_text(member.vision):
        score += W.VISION_COMPLETED

    if member.spiritual_rebirth_day:
        score += W.SPIRITUAL_REBIRTH_DAY_COMPLETED

    if _normalize_text(member.denomination_branch):
        score += W.DENOMINATION_BRANCH_COMPLETED

    # ----- activity / participation signals -----
    moment_count = _count_member_moments(member)
    score += min(moment_count * W.MOMENT_CREATED, W.MAX_MOMENT_SCORE)

    prayer_count = _count_member_prayers(member)
    score += min(prayer_count * W.PRAYER_CREATED, W.MAX_PRAYER_SCORE)

    testimony_count = _count_member_testimonies(member)
    score += min(testimony_count * W.TESTIMONY_CREATED, W.MAX_TESTIMONY_SCORE)

    friendship_count = _count_member_friendships(member)
    score += min(friendship_count * W.FRIEND_CREATED, W.MAX_FRIEND_SCORE)

    organization_count = _count_member_organization_memberships(member)
    score += min(
        organization_count * W.ORGANIZATION_MEMBERSHIP,
        W.MAX_ORGANIZATION_SCORE,
    )

    service_type_count = _count_member_service_types(member)
    score += min(
        service_type_count * W.SERVICE_TYPE_SELECTED,
        W.MAX_SERVICE_TYPE_SCORE,
    )

    if _has_completed_spiritual_gifts(member):
        score += W.SPIRITUAL_GIFTS_COMPLETED

    # ----- negative signals -----
    report_count = _count_account_reports(member.user)
    score += max(
        report_count * W.ACCOUNT_REPORT_PENALTY,
        W.MAX_REPORT_PENALTY,
    )

    return max(score, 0)