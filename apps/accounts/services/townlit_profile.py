# apps/accounts/services/townlit_profile.py

from django.contrib.contenttypes.models import ContentType

from apps.profiles.models import Member
from apps.posts.models.testimony import Testimony
from apps.profiles.models import MemberSpiritualGifts


def _normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _member_ct():
    return ContentType.objects.get_for_model(Member)


def _member_testimony_qs(member: Member):
    return Testimony.objects.filter(
        content_type=_member_ct(),
        object_id=member.id,
    )


def _has_written_testimony(member: Member) -> bool:
    return _member_testimony_qs(member).filter(
        type=Testimony.TYPE_WRITTEN,
        is_active=True,
        is_hidden=False,
    ).exists()


def _has_audio_testimony(member: Member) -> bool:
    return _member_testimony_qs(member).filter(
        type=Testimony.TYPE_AUDIO,
        is_active=True,
        is_hidden=False,
        is_converted=True,
    ).exists()


def _has_video_testimony(member: Member) -> bool:
    return _member_testimony_qs(member).filter(
        type=Testimony.TYPE_VIDEO,
        is_active=True,
        is_hidden=False,
        is_converted=True,
    ).exists()


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


def get_member_missing_townlit_requirements(member: Member) -> list[str]:
    """
    Hard requirements for TownLIT gold.

    These are mandatory. Missing any of them blocks initial gold unlock,
    and if gold is already active, missing any of them revokes gold.
    """
    missing = []

    # Must be blue verified first
    if not getattr(member.user, "is_verified_identity", False):
        missing.append("identity_verification")

    if not member.service_types.exists():
        missing.append("service_types")

    if not _normalize_text(member.biography):
        missing.append("biography")

    if not _normalize_text(member.vision):
        missing.append("vision")

    if not member.spiritual_rebirth_day:
        missing.append("spiritual_rebirth_day")

    if not _normalize_text(member.denomination_branch):
        missing.append("denomination_branch")

    if not _has_written_testimony(member):
        missing.append("written_testimony")

    if not _has_audio_testimony(member):
        missing.append("audio_testimony")

    if not _has_video_testimony(member):
        missing.append("video_testimony")

    if not _has_completed_spiritual_gifts(member):
        missing.append("spiritual_gifts")

    return missing


def has_member_townlit_hard_requirements(member: Member) -> bool:
    return len(get_member_missing_townlit_requirements(member)) == 0