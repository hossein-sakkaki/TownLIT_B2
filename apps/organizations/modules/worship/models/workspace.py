# apps/organizations/modules/worship/models/workspace.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-01.
# Last Update by Hossein Sakkaki on 2026-09-01.
#

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.organizations.constants import OrganizationModuleKey


class WorshipWorkspace(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    activation = models.OneToOneField(
        "organizations.OrganizationModuleActivation",
        on_delete=models.CASCADE,
        related_name="worship_workspace",
    )
    settings = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.activation.module.key != OrganizationModuleKey.WORSHIP:
            raise ValidationError({"activation": "Worship workspaces require a Worship module activation."})

    @property
    def organization(self):
        return self.activation.organization

    def __str__(self):
        return f"{self.activation.organization_id}:worship"
