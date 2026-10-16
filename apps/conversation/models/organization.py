# apps/conversation/models/organization.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.conversation.constants import (
    OrganizationConversationContextType,
    OrganizationConversationStatus,
    OrganizationConversationWaitingFor,
)

from .dialogue import Dialogue
from .message import Message


class OrganizationDialogueContext(models.Model):
    id = models.BigAutoField(primary_key=True)
    public_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )
    dialogue = models.OneToOneField(
        Dialogue,
        on_delete=models.CASCADE,
        related_name="organization_context",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="conversation_contexts",
    )
    context_type = models.CharField(
        max_length=30,
        choices=OrganizationConversationContextType.choices,
        db_index=True,
    )
    participant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="organization_direct_conversation_contexts",
    )

    status = models.CharField(
        max_length=20,
        choices=OrganizationConversationStatus.choices,
        default=OrganizationConversationStatus.OPEN,
        db_index=True,
    )
    waiting_for = models.CharField(
        max_length=20,
        choices=OrganizationConversationWaitingFor.choices,
        default=OrganizationConversationWaitingFor.NONE,
        db_index=True,
    )
    assigned_to_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversation_contexts",
    )

    # MySQL-safe uniqueness slot for the single Members Community.
    canonical_slot = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Organization Dialogue Context"
        verbose_name_plural = "Organization Dialogue Contexts"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "context_type",
                    "participant_user",
                ],
                name="uq_conv_org_direct_context",
            ),
            models.UniqueConstraint(
                fields=[
                    "organization",
                    "context_type",
                    "canonical_slot",
                ],
                name="uq_conv_org_community_slot",
            ),
            models.CheckConstraint(
                check=(
                    Q(
                        context_type=OrganizationConversationContextType.DIRECT,
                        participant_user__isnull=False,
                        canonical_slot__isnull=True,
                    )
                    | Q(
                        context_type=(
                            OrganizationConversationContextType.MEMBERS_COMMUNITY
                        ),
                        participant_user__isnull=True,
                        canonical_slot=1,
                        assigned_to_membership__isnull=True,
                        status=OrganizationConversationStatus.OPEN,
                        waiting_for=OrganizationConversationWaitingFor.NONE,
                    )
                ),
                name="ck_conv_org_context_shape",
            ),
        ]
        indexes = [
            models.Index(
                fields=["organization", "context_type", "status"],
                name="conv_org_ctx_type_status_idx",
            ),
            models.Index(
                fields=["participant_user", "context_type"],
                name="conv_org_ctx_participant_idx",
            ),
        ]

    def _sync_canonical_slot(self):
        self.canonical_slot = (
            1
            if self.context_type
            == OrganizationConversationContextType.MEMBERS_COMMUNITY
            else None
        )

    def clean(self):
        super().clean()
        self._sync_canonical_slot()

        errors = {}
        dialogue = self.dialogue if self.dialogue_id else None

        if self.context_type == OrganizationConversationContextType.DIRECT:
            if not self.participant_user_id:
                errors["participant_user"] = (
                    "Organization Direct requires an external participant."
                )

            if dialogue and dialogue.is_group:
                errors["dialogue"] = (
                    "Organization Direct must use a non-group dialogue."
                )

            if dialogue and self.participant_user_id:
                participants = dialogue.participants.all()
                if not participants.filter(
                    id=self.participant_user_id,
                ).exists():
                    errors["participant_user"] = (
                        "The Organization Direct participant must be stored "
                        "on the dialogue."
                    )
                elif participants.exclude(
                    id=self.participant_user_id,
                ).exists():
                    errors["dialogue"] = (
                        "Organization Direct stores only the external "
                        "participant on the dialogue."
                    )

        elif (
            self.context_type
            == OrganizationConversationContextType.MEMBERS_COMMUNITY
        ):
            if self.participant_user_id:
                errors["participant_user"] = (
                    "Members Community cannot have a direct participant."
                )

            if dialogue and not dialogue.is_group:
                errors["dialogue"] = (
                    "Members Community must use a group dialogue."
                )

            if self.status != OrganizationConversationStatus.OPEN:
                errors["status"] = (
                    "Members Community must remain open."
                )

            if self.waiting_for != OrganizationConversationWaitingFor.NONE:
                errors["waiting_for"] = (
                    "Members Community does not use direct waiting state."
                )

            if self.assigned_to_membership_id:
                errors["assigned_to_membership"] = (
                    "Members Community cannot be assigned to an operator."
                )

        if self.assigned_to_membership_id and self.organization_id:
            if (
                self.assigned_to_membership.organization_id
                != self.organization_id
            ):
                errors["assigned_to_membership"] = (
                    "Assigned membership must belong to the same organization."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._sync_canonical_slot()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("canonical_slot")
            kwargs["update_fields"] = list(update_fields)

        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.organization_id}:"
            f"{self.context_type}:"
            f"{self.dialogue_id}"
        )


class OrganizationMessageAttribution(models.Model):
    id = models.BigAutoField(primary_key=True)
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name="organization_attribution",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="message_attributions",
    )
    actor_membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_message_attributions",
    )

    actor_display_name_snapshot = models.CharField(max_length=255)
    actor_username_snapshot = models.CharField(max_length=150)
    actor_membership_public_id_snapshot = models.UUIDField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Organization Message Attribution"
        verbose_name_plural = "Organization Message Attributions"
        indexes = [
            models.Index(
                fields=["organization", "created_at"],
                name="conv_org_attr_created_idx",
            ),
        ]

    def clean(self):
        super().clean()

        errors = {}
        context = None

        if self.message_id:
            context = (
                OrganizationDialogueContext.objects
                .filter(dialogue_id=self.message.dialogue_id)
                .first()
            )

            if not context:
                errors["message"] = (
                    "Organization attribution requires an Organization "
                    "conversation context."
                )

        if context and self.organization_id:
            if context.organization_id != self.organization_id:
                errors["organization"] = (
                    "Attribution organization must match the dialogue context."
                )

        if self.actor_membership_id:
            membership = self.actor_membership

            if (
                self.organization_id
                and membership.organization_id != self.organization_id
            ):
                errors["actor_membership"] = (
                    "Actor membership must belong to the same organization."
                )

            if (
                self.message_id
                and membership.member.user_id != self.message.sender_id
            ):
                errors["actor_membership"] = (
                    "Actor membership must belong to the message sender."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.organization_id}:{self.message_id}"
