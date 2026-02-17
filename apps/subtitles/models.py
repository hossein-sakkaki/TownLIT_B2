# apps/subtitles/models.py

from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from utils.common.utils import FileUpload

from validators.mediaValidators.audio_validators import validate_audio_file
from validators.security_validators import validate_no_executable_file



# Enums for job statuses and subtitle formats ---------------------------------------------------------
class TranscriptJobStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

# Subtitle related models ------------------------------------------------
class SubtitleJobStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

# Subtitle related models ------------------------------------------------
class SubtitleFormat(models.TextChoices):
    VTT = "vtt"
    SRT = "srt"

# VideoTranscript model -------------------------------------------------
class VideoTranscript(models.Model):
    """
    One transcript per content object (video).
    Stores detected language + full text (optional).
    """
    
    STT_AUDIO = FileUpload("subtitles", "stt", "audio")

    id = models.BigAutoField(primary_key=True)

    # Generic target (e.g., Testimony, Moment)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    status = models.CharField(
        max_length=20,
        choices=TranscriptJobStatus.choices,
        default=TranscriptJobStatus.PENDING,
        db_index=True,
    )

    source_language = models.CharField(max_length=10, blank=True, default="")
    stt_engine = models.CharField(max_length=30, blank=True, default="openai")
    stt_model = models.CharField(max_length=50, blank=True, default="")
    error = models.TextField(blank=True, default="")

    full_text = models.TextField(blank=True, default="")  # Optional convenience

    stt_audio = models.FileField(
        upload_to=STT_AUDIO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_audio_file, validate_no_executable_file],
        verbose_name="STT Audio Source",
    )
    stt_audio_format = models.CharField(
        max_length=10,
        blank=True,
        default="wav",  # wav | flac | mp3
    )
    tone_profile = models.JSONField(blank=True, null=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                name="uniq_video_transcript_per_object",
            )
        ]

    def __str__(self) -> str:
        return f"Transcript<{self.content_type.app_label}.{self.content_type.model}#{self.object_id}>"

# TranscriptSegment model -----------------------------------------------
class TranscriptSegment(models.Model):
    """
    Timestamped segments (single source of truth for subtitles).
    TranslationCache can target this model's 'text' field.
    """

    id = models.BigAutoField(primary_key=True)

    transcript = models.ForeignKey(
        VideoTranscript,
        on_delete=models.CASCADE,
        related_name="segments",
    )
    idx = models.PositiveIntegerField(db_index=True)

    start_ms = models.PositiveIntegerField()
    end_ms = models.PositiveIntegerField()

    text = models.TextField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transcript", "idx"],
                name="uniq_transcript_segment_idx",
            )
        ]
        indexes = [
            models.Index(fields=["transcript", "idx"], name="segment_order_idx"),
        ]

    def __str__(self) -> str:
        return f"Segment<{self.transcript_id}#{self.idx} {self.start_ms}-{self.end_ms}>"

# SubtitleTrack model ---------------------------------------------------
class SubtitleTrack(models.Model):
    """
    Generated subtitle file (VTT/SRT) per language.
    """

    id = models.BigAutoField(primary_key=True)

    transcript = models.ForeignKey(
        VideoTranscript,
        on_delete=models.CASCADE,
        related_name="subtitle_tracks",
    )

    target_language = models.CharField(max_length=10, db_index=True)

    fmt = models.CharField(
        max_length=10,
        choices=SubtitleFormat.choices,
        default=SubtitleFormat.VTT,
    )

    status = models.CharField(
        max_length=20,
        choices=SubtitleJobStatus.choices,
        default=SubtitleJobStatus.PENDING,
        db_index=True,
    )

    # Output metadata
    engine = models.CharField(max_length=30, blank=True, default="aws+llm")
    prompt_version = models.CharField(max_length=20, blank=True, default="")
    llm_model = models.CharField(max_length=50, blank=True, default="")
    is_humanized = models.BooleanField(default=False, db_index=True)

    # Store generated content (quick start)
    # Later you can store file in S3 + keep url/key here.
    content = models.TextField(blank=True, default="")

    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transcript", "target_language", "fmt"],
                name="uniq_subtitle_track_lang_fmt",
            )
        ]

    def __str__(self) -> str:
        return f"Subtitle<{self.transcript_id} {self.target_language} {self.fmt}>"



# VoiceTrack model --------------------------------------------------------------------------------------------
class VoiceJobStatus(models.TextChoices):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"

# VoiceTrack model --------------------------------------------------------------------------------------------
class VoiceTrack(models.Model):
    """
    Generated voice (TTS) for a subtitle track.
    """
    VOICE_AUDIO = FileUpload("subtitles", "voice", "audio")

    id = models.BigAutoField(primary_key=True)

    transcript = models.ForeignKey(
        VideoTranscript,
        on_delete=models.CASCADE,
        related_name="voice_tracks",
    )

    subtitle_track = models.ForeignKey(
        SubtitleTrack,
        on_delete=models.CASCADE,
        related_name="voice_tracks",
    )

    target_language = models.CharField(max_length=10, db_index=True)
    owner_gender = models.CharField(
        max_length=10,
        blank=True,
        default="",  # "Male" | "Female" | ""
        db_index=True,
    )
    provider = models.CharField(
        max_length=30,
        default="openai",  # openai | aws | elevenlabs (future)
    )

    voice_id = models.CharField(
        max_length=50,
        blank=True,
        default="",  # e.g. alloy, nova, etc.
    )

    status = models.CharField(
        max_length=20,
        choices=VoiceJobStatus.choices,
        default=VoiceJobStatus.PENDING,
        db_index=True,
    )

    audio = models.FileField(
        upload_to=VOICE_AUDIO.dir_upload,
        null=True,
        blank=True,
        validators=[validate_audio_file, validate_no_executable_file],
    )

    spoken_text = models.TextField(
        blank=True,
        default="",
        help_text="Humanized text optimized for speech (TTS)",
    )
    
    duration_ms = models.PositiveIntegerField(null=True, blank=True)

    error = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subtitle_track", "provider", "voice_id"],
                name="uniq_voice_per_subtitle_provider",
            )
        ]

    def __str__(self) -> str:
        return f"Voice<{self.subtitle_track_id} {self.target_language}>"
