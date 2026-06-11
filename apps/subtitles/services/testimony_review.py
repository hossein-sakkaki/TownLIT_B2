# apps/subtitles/services/testimony_review.py

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from apps.subtitles.models import (
    VideoTranscript,
    TranscriptContentReviewStatus,
    TranscriptDetectedContentType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------

# Approved only when the classifier is reasonably confident.
APPROVAL_CONFIDENCE_MIN = 0.55

# Rejected/deleted only when the classifier is highly confident.
# Anything below this becomes needs_review to avoid false deletion.
AUTO_REJECT_CONFIDENCE_MIN = 0.78


@dataclass(frozen=True)
class TestimonyReviewResult:
    status: str
    detected_content_type: str
    confidence: float
    reason: str
    ai_processing_allowed: bool


# ---------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------

def is_testimony_transcript(
    transcript: VideoTranscript,
) -> bool:
    try:
        ct = transcript.content_type
        return ct.app_label == "posts" and ct.model == "testimony"
    except Exception:
        return False


def is_transcript_ai_allowed(
    transcript: VideoTranscript,
) -> bool:
    """
    Central guard for subtitle/voice generation.
    """
    if not is_testimony_transcript(transcript):
        return False

    return (
        transcript.ai_processing_allowed is True
        and transcript.content_review_status == TranscriptContentReviewStatus.APPROVED
    )


def assert_transcript_ai_allowed(
    transcript: VideoTranscript,
) -> None:
    if is_transcript_ai_allowed(transcript):
        return

    raise RuntimeError(
        "AI subtitle/voice generation is blocked because this content "
        "has not been approved as a personal testimony."
    )


# ---------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------

def _normalize_confidence(
    value,
) -> float:
    try:
        confidence = float(value or 0.0)
    except Exception:
        confidence = 0.0

    return max(0.0, min(1.0, confidence))


def _normalize_status(
    value,
) -> str:
    status = str(value or TranscriptContentReviewStatus.NEEDS_REVIEW).strip()

    allowed_statuses = {
        TranscriptContentReviewStatus.APPROVED,
        TranscriptContentReviewStatus.REJECTED,
        TranscriptContentReviewStatus.NEEDS_REVIEW,
    }

    if status not in allowed_statuses:
        return TranscriptContentReviewStatus.NEEDS_REVIEW

    return status


def _normalize_detected_type(
    value,
) -> str:
    detected = str(value or TranscriptDetectedContentType.UNKNOWN).strip()

    allowed_types = {
        TranscriptDetectedContentType.PERSONAL_TESTIMONY,
        TranscriptDetectedContentType.WORSHIP_SONG,
        TranscriptDetectedContentType.MUSIC,
        TranscriptDetectedContentType.TEACHING,
        TranscriptDetectedContentType.PRAYER,
        TranscriptDetectedContentType.OTHER,
        TranscriptDetectedContentType.UNKNOWN,
    }

    if detected not in allowed_types:
        return TranscriptDetectedContentType.UNKNOWN

    return detected


def _finalize_review_result(
    *,
    status: str,
    detected_content_type: str,
    confidence: float,
    reason: str,
) -> TestimonyReviewResult:
    """
    Final safety policy.

    Important:
    - Auto-delete/reject only when confidence is high.
    - Low-confidence rejection becomes needs_review.
    - Music presence alone must not cause rejection.
    - Approved content must be personal_testimony with enough confidence.
    """
    status = _normalize_status(status)
    detected_content_type = _normalize_detected_type(detected_content_type)
    confidence = _normalize_confidence(confidence)
    reason = (reason or "").strip()[:2000]

    # -------------------------------------------------
    # Approval policy
    # -------------------------------------------------
    ai_allowed = (
        status == TranscriptContentReviewStatus.APPROVED
        and detected_content_type == TranscriptDetectedContentType.PERSONAL_TESTIMONY
        and confidence >= APPROVAL_CONFIDENCE_MIN
    )

    if status == TranscriptContentReviewStatus.APPROVED and not ai_allowed:
        status = TranscriptContentReviewStatus.NEEDS_REVIEW
        ai_allowed = False

        if not reason:
            reason = (
                "The content may be a testimony, but the classifier was not "
                "confident enough to approve it automatically."
            )

    # -------------------------------------------------
    # Rejection policy
    # -------------------------------------------------
    if status == TranscriptContentReviewStatus.REJECTED:
        clearly_rejectable_type = detected_content_type in {
            TranscriptDetectedContentType.WORSHIP_SONG,
            TranscriptDetectedContentType.MUSIC,
            TranscriptDetectedContentType.TEACHING,
            TranscriptDetectedContentType.PRAYER,
            TranscriptDetectedContentType.OTHER,
            TranscriptDetectedContentType.UNKNOWN,
        }

        if not clearly_rejectable_type:
            status = TranscriptContentReviewStatus.NEEDS_REVIEW
            ai_allowed = False

            if not reason:
                reason = (
                    "The content was not clearly rejectable and needs manual review."
                )

        elif confidence < AUTO_REJECT_CONFIDENCE_MIN:
            status = TranscriptContentReviewStatus.NEEDS_REVIEW
            ai_allowed = False

            if not reason:
                reason = (
                    "The content may not be a personal testimony, but confidence "
                    "was not high enough for automatic removal."
                )

        else:
            ai_allowed = False

    # -------------------------------------------------
    # Needs review policy
    # -------------------------------------------------
    if status == TranscriptContentReviewStatus.NEEDS_REVIEW:
        ai_allowed = False

        if not reason:
            reason = "This testimony needs manual review before AI processing."

    return TestimonyReviewResult(
        status=status,
        detected_content_type=detected_content_type,
        confidence=confidence,
        reason=reason,
        ai_processing_allowed=ai_allowed,
    )


# ---------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------

def review_testimony_transcript_text(
    *,
    text: str,
    source_language: str = "",
) -> TestimonyReviewResult:
    """
    Review transcript text and decide whether it is a personal testimony.

    Uses OpenAI if available. Falls back to needs_review.
    """
    clean_text = (text or "").strip()

    if not clean_text:
        return TestimonyReviewResult(
            status=TranscriptContentReviewStatus.NEEDS_REVIEW,
            detected_content_type=TranscriptDetectedContentType.UNKNOWN,
            confidence=0.0,
            reason="Transcript text is empty.",
            ai_processing_allowed=False,
        )

    try:
        return _review_with_openai(
            text=clean_text,
            source_language=source_language,
        )
    except Exception as exc:
        logger.warning(
            "Testimony review OpenAI classifier failed: %s",
            exc,
            exc_info=True,
        )

        # Safe fallback: never auto-delete on classifier failure.
        return TestimonyReviewResult(
            status=TranscriptContentReviewStatus.NEEDS_REVIEW,
            detected_content_type=TranscriptDetectedContentType.UNKNOWN,
            confidence=0.0,
            reason="Automatic review failed; manual review is required.",
            ai_processing_allowed=False,
        )


def _review_with_openai(
    *,
    text: str,
    source_language: str = "",
) -> TestimonyReviewResult:
    """
    OpenAI JSON classifier.

    The goal is not theology grading.
    The goal is only to prevent worship songs/music/general content
    from triggering testimony-only subtitle/voice pipelines.
    """
    from openai import OpenAI

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=api_key)

    prompt = f"""
You are a content classifier for a Christian testimony feature.

Decide whether the transcript is a personal testimony.

A personal testimony usually contains first-person lived experience:
- personal background, struggle, prayer, faith journey, repentance, healing, change, or God's work in the speaker's life
- narrative language such as "I", "my life", "I experienced", "God helped me", etc.
- a personal story of faith, change, struggle, healing, hope, or spiritual journey

Reject or flag content that is mainly:
- worship song lyrics
- music lyrics
- repeated chorus/verse
- teaching/sermon
- generic prayer
- announcement
- unrelated content

Very important:
- A valid personal testimony may include short intro music, outro music, background music, or podcast-style opening/ending.
- Do NOT reject content only because music is present.
- If there is meaningful first-person testimony speech, classify it as personal_testimony.
- If music is present but the spoken testimony is unclear, too short, or hard to judge, use needs_review instead of rejected.
- If the transcript is mostly lyrics, repeated chorus, worship song text, or music content without a personal testimony narrative, use rejected.
- If there is no discernible speech or no meaningful transcript content, use rejected with high confidence.
- If uncertain, use needs_review.
- Be conservative with automatic approval and conservative with automatic rejection.

Return ONLY valid JSON with this exact shape:
{{
  "status": "approved" | "rejected" | "needs_review",
  "detected_content_type": "personal_testimony" | "worship_song" | "music" | "teaching" | "prayer" | "other" | "unknown",
  "confidence": 0.0,
  "reason": "short reason"
}}

Rules:
- If it is clearly a personal testimony, status = approved.
- If it is clearly worship/song/music with no meaningful personal testimony speech, status = rejected.
- If it appears to have music plus possible testimony speech but you are unsure, status = needs_review.
- If it is teaching/sermon/prayer/announcement rather than personal testimony, status = rejected only when confidence is high; otherwise needs_review.
- Do not reject only because the transcript is short, unless it clearly contains no meaningful testimony content.
- Do not reject only because the speaker mentions worship, prayer, church, or a song.
- Rejection should require high confidence.

Source language: {source_language or "unknown"}

Transcript:
{text[:12000]}
""".strip()

    response = client.chat.completions.create(
        model=getattr(
            settings,
            "OPENAI_TESTIMONY_REVIEW_MODEL",
            "gpt-4o-mini",
        ),
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": "Return only strict JSON. No markdown.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)

    return _finalize_review_result(
        status=data.get("status"),
        detected_content_type=data.get("detected_content_type"),
        confidence=data.get("confidence"),
        reason=data.get("reason"),
    )


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------

def review_and_update_transcript(
    transcript: VideoTranscript,
) -> VideoTranscript:
    """
    Review a transcript and persist the result.
    """
    if not is_testimony_transcript(transcript):
        transcript.content_review_status = TranscriptContentReviewStatus.REJECTED
        transcript.detected_content_type = TranscriptDetectedContentType.OTHER
        transcript.content_review_confidence = 1.0
        transcript.content_review_reason = (
            "Subtitle/voice AI pipeline is only enabled for Testimony content."
        )
        transcript.ai_processing_allowed = False
        transcript.content_reviewed_at = timezone.now()
        transcript.save(
            update_fields=[
                "content_review_status",
                "detected_content_type",
                "content_review_confidence",
                "content_review_reason",
                "ai_processing_allowed",
                "content_reviewed_at",
                "updated_at",
            ]
        )
        return transcript

    result = review_testimony_transcript_text(
        text=transcript.full_text or "",
        source_language=transcript.source_language or "",
    )

    transcript.content_review_status = result.status
    transcript.detected_content_type = result.detected_content_type
    transcript.content_review_confidence = result.confidence
    transcript.content_review_reason = result.reason
    transcript.ai_processing_allowed = result.ai_processing_allowed
    transcript.content_reviewed_at = timezone.now()

    transcript.save(
        update_fields=[
            "content_review_status",
            "detected_content_type",
            "content_review_confidence",
            "content_review_reason",
            "ai_processing_allowed",
            "content_reviewed_at",
            "updated_at",
        ]
    )

    return transcript