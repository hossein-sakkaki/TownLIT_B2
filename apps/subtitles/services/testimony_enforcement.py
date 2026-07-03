# apps/subtitles/services/testimony_enforcement.py

from __future__ import annotations

import logging
import os
from typing import Iterable

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.files.storage import default_storage
from django.db import transaction

from apps.media_conversion.models import MediaConversionJob
from apps.subtitles.models import (
    VideoTranscript,
    VoiceTrack,
    TranscriptContentReviewStatus,
)
from apps.notifications.services.ui_link_resolver import (
    build_member_profile_link,
    build_testimony_create_link,
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------
def _clean_key(value) -> str | None:
    if not value:
        return None

    raw = getattr(value, "name", value)

    if not raw:
        return None

    key = str(raw).strip().lstrip("/")
    return key or None


def _delete_storage_key(key: str | None, *, label: str) -> None:
    key = _clean_key(key)

    if not key:
        return

    try:
        if default_storage.exists(key):
            default_storage.delete(key)
    except Exception:
        logger.exception("Failed deleting %s: %s", label, key)


def _delete_storage_tree(path: str | None, *, label: str) -> None:
    """
    Delete a file and its folder-like prefix.
    Useful for HLS master.m3u8 outputs.
    """
    path = _clean_key(path)

    if not path:
        return

    _delete_storage_key(path, label=label)

    prefix = path

    if "." in os.path.basename(path):
        prefix = os.path.dirname(path)

    prefix = prefix.strip("/")

    if not prefix:
        return

    _delete_prefix_recursive(prefix, label=label)


def _delete_prefix_recursive(prefix: str, *, label: str) -> None:
    prefix = prefix.strip("/")

    if not prefix:
        return

    try:
        directories, files = default_storage.listdir(prefix)
    except Exception:
        return

    for filename in files:
        _delete_storage_key(
            f"{prefix}/{filename}",
            label=f"{label}.file",
        )

    for directory in directories:
        _delete_prefix_recursive(
            f"{prefix}/{directory}",
            label=f"{label}.dir",
        )


def _target_field_keys(target, field_names: Iterable[str]) -> list[str]:
    keys: list[str] = []

    if target is None:
        return keys

    for field_name in field_names:
        try:
            if not hasattr(target, field_name):
                continue

            key = _clean_key(getattr(target, field_name, None))
            if key:
                keys.append(key)
        except Exception:
            continue

    return keys


# ---------------------------------------------------------------------
# Owner helpers
# ---------------------------------------------------------------------
def _resolve_owner_user(target):
    """
    Best-effort owner resolver for Testimony-like content.
    """
    if target is None:
        return None

    candidates = []

    for attr in ("user", "owner", "created_by", "author"):
        try:
            value = getattr(target, attr, None)
            if value is not None:
                candidates.append(value)
        except Exception:
            pass

    try:
        content_object = getattr(target, "content_object", None)
        if content_object is not None:
            for attr in ("user", "owner", "created_by", "author"):
                try:
                    value = getattr(content_object, attr, None)
                    if value is not None:
                        candidates.append(value)
                except Exception:
                    pass
    except Exception:
        pass

    for candidate in candidates:
        try:
            if hasattr(candidate, "email"):
                return candidate

            user = getattr(candidate, "user", None)
            if user is not None and hasattr(user, "email"):
                return user
        except Exception:
            continue

    return None


TESTIMONY_VIDEO_REJECTED_NOTIFICATION_TYPE = "testimony_video_rejected"


def _build_rejected_testimony_links(
    *,
    user,
) -> dict[str, str]:
    """
    Build separate links for app/internal notification, push, and email.
    """
    username = getattr(user, "username", None) or None

    in_app_link = build_testimony_create_link(
        username=username,
        kind="video",
        source="testimony_rejected",
    )

    profile_fallback_link = build_member_profile_link(
        username=username,
    )

    return {
        # Stored on Notification.link and used by WS/in-app + push data.
        "in_app_link": in_app_link or profile_fallback_link,

        # Explicit fallback if the app cannot route create intent.
        "profile_link": profile_fallback_link,

        # Email should use public website root for now.
        "email_link": "https://townlit.com",
    }


def _build_rejected_testimony_message(
    *,
    reason: str,
) -> str:
    """
    User-facing notification/email body.
    """
    clean_reason = (reason or "").strip()

    if not clean_reason:
        clean_reason = "This video did not appear to be a personal testimony."

    return (
        "Your video testimony was not accepted because it did not appear to be "
        "a personal testimony. The testimony section is designed for your own "
        "story — your experience, faith journey, prayer, change, or what God "
        "has done in your life. You can upload a new video testimony from your "
        "profile. If you believe this was a mistake, please contact TownLIT support.\n\n"
        f"Reason: {clean_reason}"
    )


def _build_testimony_create_link(
    *,
    user,
) -> str:
    """
    Frontend link that encourages the user to upload a real video testimony.

    Keep this centralized so website/iOS deep-link routing can evolve later.
    """
    username = getattr(user, "username", None) or "user"

    # Web fallback: user profile with creation intent.
    # Adjust only here if your frontend route changes.
    return (
        f"/profiles/members/profile"
        f"?create=testimony"
        f"&kind=video"
        f"&source=testimony_rejected"
        f"&u={username}"
    )


def _build_rejected_testimony_message(
    *,
    reason: str,
) -> str:
    """
    User-facing notification/email body.
    """
    clean_reason = (reason or "").strip()

    if not clean_reason:
        clean_reason = "This video did not appear to be a personal testimony."

    return (
        "Your video testimony was not accepted because it did not appear to be "
        "a personal testimony. The testimony section is designed for your own "
        "story — your experience, faith journey, prayer, change, or what God "
        "has done in your life. You can upload a new video testimony from your "
        "profile. If you believe this was a mistake, please contact TownLIT support.\n\n"
        f"Reason: {clean_reason}"
    )

def _notify_user_about_rejected_testimony(
    *,
    user,
    reason: str,
) -> None:
    """
    Notify the owner that their video testimony was rejected.

    Uses TownLIT's centralized notification system:
    - DB notification
    - WebSocket/in-app notification
    - Push notification
    - Email through notification email task

    Must never block deletion/enforcement.
    """
    if user is None:
        return

    try:
        # Lazy import prevents circular imports during Django app loading.
        from apps.notifications.services.services import (
            create_and_dispatch_notification,
        )

        links = _build_rejected_testimony_links(user=user)
        message = _build_rejected_testimony_message(reason=reason)

        create_and_dispatch_notification(
            recipient=user,
            actor=None,
            notif_type=TESTIMONY_VIDEO_REJECTED_NOTIFICATION_TYPE,
            message=message,
            target_obj=None,
            action_obj=None,

            # In-app + push data link.
            link=links["in_app_link"],

            # Always create a fresh notice for this event.
            dedupe=False,

            extra_payload={
                "event": "testimony_video_rejected",
                "reason": (reason or "")[:500],
                "next_action": "upload_video_testimony",
                "support_hint": "contact_support_if_mistake",

                # App/internal routing.
                "in_app_link": links["in_app_link"],
                "profile_link": links["profile_link"],

                # Email routing.
                "email_link": links["email_link"],
                "web_link": links["email_link"],
            },
        )

    except Exception:
        logger.exception(
            "Rejected testimony notification failed user=%s",
            getattr(user, "pk", None),
        )

# ---------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------
def _safe_target_for_transcript(transcript: VideoTranscript):
    try:
        return transcript.content_object
    except Exception:
        return None


def _is_posts_testimony_transcript(transcript: VideoTranscript) -> bool:
    try:
        return (
            transcript.content_type.app_label == "posts"
            and transcript.content_type.model == "testimony"
        )
    except Exception:
        return False


def is_testimony_review_approved_for_display(target) -> bool:
    """
    Use this in Testimony serializers/profile queries to avoid exposing
    pending/rejected testimony videos as profile banner content.
    """
    if target is None:
        return False

    try:
        ct = ContentType.objects.get_for_model(target.__class__)
        transcript = (
            VideoTranscript.objects
            .filter(content_type=ct, object_id=target.pk)
            .only(
                "id",
                "content_review_status",
                "ai_processing_allowed",
            )
            .first()
        )

        if not transcript:
            return False

        return (
            transcript.content_review_status == TranscriptContentReviewStatus.APPROVED
            and transcript.ai_processing_allowed is True
        )
    except Exception:
        return False


# ---------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------
def delete_rejected_testimony_media(
    transcript: VideoTranscript,
    *,
    reason: str = "",
) -> None:
    """
    Delete a rejected Testimony video and all related conversion/subtitle assets.

    Deletes:
    - Testimony DB row
    - VideoTranscript row
    - SubtitleTrack/VoiceTrack rows via cascade
    - MediaConversionJob rows for the target
    - target media files: video/audio/image/thumbnail
    - transcript STT audio
    - generated voice audio
    - HLS output folder(s)
    """
    if not transcript:
        return

    transcript = (
        VideoTranscript.objects
        .select_related("content_type")
        .filter(pk=transcript.pk)
        .first()
    )

    if not transcript:
        return

    if not _is_posts_testimony_transcript(transcript):
        return

    target = _safe_target_for_transcript(transcript)

    if target is None:
        # Orphan transcript. Remove it safely.
        transcript.delete()
        return

    user = _resolve_owner_user(target)

    reason_text = (
        reason
        or transcript.content_review_reason
        or "This content was not approved as a personal testimony."
    )

    # Notify before deleting the target.
    _notify_user_about_rejected_testimony(
        user=user,
        reason=reason_text,
    )

    # Collect storage keys before DB deletion.
    target_keys = _target_field_keys(
        target,
        field_names=[
            "video",
            "audio",
            "thumbnail",
            "image",
        ],
    )

    transcript_stt_key = _clean_key(transcript.stt_audio)

    voice_audio_keys = list(
        VoiceTrack.objects
        .filter(transcript=transcript)
        .exclude(audio="")
        .values_list("audio", flat=True)
    )

    ct = transcript.content_type
    object_id = transcript.object_id

    job_output_keys = list(
        MediaConversionJob.objects
        .filter(content_type=ct, object_id=object_id)
        .exclude(output_path__isnull=True)
        .exclude(output_path="")
        .values_list("output_path", flat=True)
    )

    job_source_keys = list(
        MediaConversionJob.objects
        .filter(content_type=ct, object_id=object_id)
        .exclude(source_path__isnull=True)
        .exclude(source_path="")
        .values_list("source_path", flat=True)
    )

    with transaction.atomic():
        # Remove conversion job rows for this target.
        MediaConversionJob.objects.filter(
            content_type=ct,
            object_id=object_id,
        ).delete()

        # Remove transcript + tracks.
        transcript.delete()

        # Remove rejected testimony target.
        target.delete()

    # Storage cleanup outside transaction.
    for key in set(target_keys):
        _delete_storage_tree(
            key,
            label="rejected_testimony.target_media",
        )

    _delete_storage_key(
        transcript_stt_key,
        label="rejected_testimony.stt_audio",
    )

    for key in set(voice_audio_keys):
        _delete_storage_key(
            key,
            label="rejected_testimony.voice_audio",
        )

    for key in set(job_source_keys):
        _delete_storage_key(
            key,
            label="rejected_testimony.job_source",
        )

    for key in set(job_output_keys):
        _delete_storage_tree(
            key,
            label="rejected_testimony.job_output",
        )

    logger.warning(
        "🧹 Rejected testimony deleted target=%s[%s] user=%s reason=%s",
        target.__class__.__name__,
        getattr(target, "pk", None),
        getattr(user, "pk", None),
        reason_text,
    )


def enforce_testimony_review_outcome(
    transcript: VideoTranscript,
) -> str:
    """
    Apply post-review policy.

    approved:
      keep target and allow subtitle/voice pipeline

    rejected:
      delete target, transcript, jobs, files and notify user

    needs_review:
      keep target for admin review, but UI must not expose it publicly
    """
    if not transcript:
        return "missing"

    status = transcript.content_review_status

    if status == TranscriptContentReviewStatus.APPROVED:
        return "approved"

    if status == TranscriptContentReviewStatus.REJECTED:
        delete_rejected_testimony_media(
            transcript,
            reason=transcript.content_review_reason,
        )
        return "deleted"

    if status == TranscriptContentReviewStatus.NEEDS_REVIEW:
        return "needs_review"

    return "pending"