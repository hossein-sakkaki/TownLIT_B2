# apps/audio_catalog/models/usage.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from __future__ import annotations
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from .base import PublicIDTimestampedModel


class AudioUsageGrant(PublicIDTimestampedModel):
    class Status(models.TextChoices): ACTIVE="active","Active"; REVOKED="revoked","Revoked"; REPLACED="replaced","Replaced"
    content_type=models.ForeignKey(ContentType,on_delete=models.PROTECT,related_name="+")
    object_id=models.PositiveBigIntegerField()
    content_object=GenericForeignKey("content_type","object_id")
    track=models.ForeignKey("audio_catalog.MusicTrack",on_delete=models.PROTECT,related_name="usage_grants")
    variant=models.ForeignKey("audio_catalog.MusicTrackVariant",null=True,blank=True,on_delete=models.PROTECT,related_name="usage_grants")
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.ACTIVE,db_index=True)
    active_slot=models.PositiveSmallIntegerField(null=True,blank=True,editable=False)
    clip_start_ms=models.PositiveIntegerField(default=0)
    clip_duration_ms=models.PositiveIntegerField()
    music_volume=models.DecimalField(max_digits=5,decimal_places=4,default=1)
    source_audio_volume=models.DecimalField(max_digits=5,decimal_places=4,default=1)
    fade_in_ms=models.PositiveIntegerField(default=0); fade_out_ms=models.PositiveIntegerField(default=0)
    track_version_snapshot=models.PositiveIntegerField(); title_snapshot=models.CharField(max_length=180); artist_snapshot=models.CharField(max_length=180,blank=True,default="")
    rights_snapshot=models.JSONField(default=dict); technical_snapshot=models.JSONField(default=dict)
    granted_to=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="audio_usage_grants")
    revoked_at=models.DateTimeField(null=True,blank=True); revoke_reason=models.CharField(max_length=240,blank=True,default="")
    analytics_activated_at=models.DateTimeField(null=True,blank=True,editable=False,db_index=True,help_text="Set after activation analytics were counted.")
    analytics_revoked_at=models.DateTimeField(null=True,blank=True,editable=False,db_index=True,help_text="Set after active usage analytics were decremented.")

    def _sync_active_slot(self):
        expected = 1 if self.status == self.Status.ACTIVE else None; changed = self.active_slot != expected; self.active_slot = expected; return changed
    def save(self,*args,**kwargs):
        changed=self._sync_active_slot()
        if changed and kwargs.get("update_fields") is not None: kwargs["update_fields"] = list(dict.fromkeys([*kwargs["update_fields"],"active_slot"]))
        return super().save(*args,**kwargs)
    class Meta:
        ordering=["-created_at","-id"]
        indexes=[models.Index(fields=("content_type","object_id","status")),models.Index(fields=("track","status","created_at")),models.Index(fields=("granted_to","created_at")),models.Index(fields=("status","analytics_activated_at"))]
        constraints=[models.UniqueConstraint(fields=("content_type","object_id","active_slot"),name="audio_one_active_usage_per_content"),models.CheckConstraint(check=Q(clip_duration_ms__gt=0),name="audio_usage_duration_gt_zero")]
    def __str__(self): return f"{self.track.title} · {self.content_type_id}:{self.object_id}"
