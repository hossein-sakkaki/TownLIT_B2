from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from .constants import (
    COLLABORATION_TYPE_CHOICES,
    COLLABORATION_MODE_CHOICES,
    COLLABORATION_STATUS_CHOICES,
    COLLABORATION_STATUS_NEW,
    JOB_STATUS_CHOICES,
    JOB_STATUS_NEW,
    COLLABORATION_AVAILABILITY_CHOICES,
    AVAILABILITY_5
)
from django.contrib.auth import get_user_model

CustomUser = get_user_model()




class CollaborationRequest(models.Model):
    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)

    full_name = models.CharField(max_length=100, blank=True, null=True,)
    email = models.EmailField(blank=True, null=True,)
    phone_number = models.CharField(max_length=20, blank=True, null=True,)
    country = models.CharField(max_length=100, blank=True, null=True,)
    city = models.CharField(max_length=100, blank=True, null=True,)

    collaboration_type = models.CharField(max_length=50, choices=COLLABORATION_TYPE_CHOICES)
    collaboration_mode = models.CharField(max_length=20, choices=COLLABORATION_MODE_CHOICES, default='online')
    availability = models.CharField(max_length=10, choices=COLLABORATION_AVAILABILITY_CHOICES, blank=True, null=True, default=AVAILABILITY_5)
    message = models.TextField(blank=True)
    allow_contact = models.BooleanField(default=True)

    status = models.CharField(max_length=20, choices=COLLABORATION_STATUS_CHOICES, default=COLLABORATION_STATUS_NEW)
    admin_comment = models.TextField(blank=True, null=True,)
    admin_note = models.TextField(blank=True, null=True,)
    last_reviewed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="collaboration_last_reviewed"
    )

    review_logs = GenericRelation("moderation.ReviewLog")

    is_active = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.collaboration_type})"


class JobApplication(models.Model):
    user = models.ForeignKey(CustomUser, null=True, blank=True, on_delete=models.SET_NULL)

    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    resume = models.FileField(upload_to='resumes/')
    cover_letter = models.TextField(blank=True)
    position = models.CharField(max_length=100)

    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default=JOB_STATUS_NEW)
    admin_comment = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    last_reviewed_by = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="job_application_last_reviewed"
    )

    review_logs = GenericRelation("moderation.ReviewLog")

    is_active = models.BooleanField(default=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} - {self.position}"


# Review log: shared across all moderateable models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

class ReviewLog(models.Model):
    admin = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name="review_logs")
    action = models.CharField(max_length=100)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Generic FK
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")

    def __str__(self):
        return f"{self.admin} → {self.content_type} | {self.action} @ {self.created_at:%Y-%m-%d}"
