# apps/audio_catalog/models/contributors.py
from django.db import models
from django.db.models import Q
from .base import PublicIDTimestampedModel

class AudioContributor(PublicIDTimestampedModel):
    class Kind(models.TextChoices):
        PERSON = "person", "Person"
        ORGANIZATION = "organization", "Organization"
        AI_PROVIDER = "ai_provider", "AI Provider"
        UNKNOWN = "unknown", "Unknown"

    display_name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    website_url = models.URLField(blank=True)
    external_reference = models.CharField(max_length=220, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("display_name", "id")

    def __str__(self):
        return self.display_name

class TrackContributor(PublicIDTimestampedModel):
    class Role(models.TextChoices):
        PRIMARY_ARTIST = "primary_artist", "Primary Artist"
        COMPOSER = "composer", "Composer"
        LYRICIST = "lyricist", "Lyricist"
        PRODUCER = "producer", "Producer"
        ARRANGER = "arranger", "Arranger"
        PERFORMER = "performer", "Performer"
        MIX_ENGINEER = "mix_engineer", "Mix Engineer"
        MASTERING_ENGINEER = "mastering_engineer", "Mastering Engineer"
        AI_PROVIDER = "ai_provider", "AI Provider"
        CREATIVE_DIRECTOR = "creative_director", "Creative Director"
        OTHER = "other", "Other"

    track = models.ForeignKey("audio_catalog.MusicTrack", on_delete=models.CASCADE, related_name="contributor_links")
    contributor = models.ForeignKey(AudioContributor, on_delete=models.PROTECT, related_name="track_links")
    role = models.CharField(max_length=32, choices=Role.choices, db_index=True)
    credit_text = models.CharField(max_length=220, blank=True)
    share_basis_points = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "role", "id")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "track",
                    "contributor",
                    "role",
                ),
                name="audio_unique_track_contributor_role",
            ),
            models.CheckConstraint(
                check=Q(
                    share_basis_points__lte=10000
                ),
                name="audio_contributor_share_lte_10000",
            ),
        ]
