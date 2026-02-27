# apps/advancement/models/interaction.py

from django.db import models
import uuid
from django.conf import settings
from .external_entity import ExternalEntity


class InteractionLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    INTERACTION_TYPE_CHOICES = (
        ("EMAIL", "Email"),
        ("CALL", "Call"),
        ("MEETING", "Meeting"),
        ("FORM_SUBMISSION", "Form Submission"),
        ("EVENT", "Event"),
        ("OTHER", "Other"),
    )

    STATUS_CHOICES = (
        ("OPEN", "Open"),
        ("WAITING", "Waiting"),
        ("DONE", "Done"),
    )

    external_entity = models.ForeignKey(
        ExternalEntity, on_delete=models.CASCADE, related_name="interactions"
    )

    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPE_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="OPEN")

    subject = models.CharField(max_length=255, blank=True)
    summary = models.TextField()

    occurred_at = models.DateTimeField(null=True, blank=True)
    next_action = models.CharField(max_length=255, blank=True)
    next_action_date = models.DateField(null=True, blank=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="advancement_assigned_interactions"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="advancement_created_interactions"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.external_entity.name} - {self.interaction_type}"