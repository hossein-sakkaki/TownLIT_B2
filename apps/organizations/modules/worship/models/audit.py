# apps/organizations/modules/worship/models/audit.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

from django.conf import settings
from django.db import models

from apps.organizations.modules.worship.constants import WorshipAuditEvent


class WorshipAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    workspace = models.ForeignKey("organizations.WorshipWorkspace", on_delete=models.CASCADE, related_name="audit_logs")
    event = models.CharField(max_length=60, choices=WorshipAuditEvent.choices, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="worship_audit_actions")
    membership = models.ForeignKey("organizations.OrganizationMembership", null=True, blank=True, on_delete=models.SET_NULL, related_name="worship_audit_logs")
    entity_type = models.CharField(max_length=60, db_index=True)
    entity_public_id = models.UUIDField(null=True, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [models.Index(fields=("workspace", "event", "created_at")), models.Index(fields=("workspace", "entity_type", "entity_public_id"))]

    def __str__(self):
        return f"{self.workspace_id}:{self.event}:{self.entity_type}"
