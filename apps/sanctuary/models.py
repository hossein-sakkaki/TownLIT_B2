# apps/sanctuary/models.py

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from apps.sanctuary.constants.targets import REQUEST_TYPE_CHOICES
from apps.sanctuary.constants.states import REQUEST_STATUS_CHOICES, PENDING

CustomUser = get_user_model()


# Sanctuary Participant Profile ------------------------------------------------------------
class SanctuaryParticipantProfile(models.Model):
    """
    Participation profile for Sanctuary council pool.
    Designed to be extensible (settings/config + audit hooks).
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sanctuary_participation",
    )

    # User opt-in (wants to be in council pool)
    is_participant = models.BooleanField(default=False)
    participant_opted_in_at = models.DateTimeField(null=True, blank=True)
    participant_opted_out_at = models.DateTimeField(null=True, blank=True)

    # TownLIT eligibility gate (admin/system can block)
    is_eligible = models.BooleanField(default=True)
    eligible_changed_at = models.DateTimeField(null=True, blank=True)
    eligible_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sanctuary_eligibility_changes",
        limit_choices_to={"is_staff": True},
    )
    eligible_reason = models.TextField(null=True, blank=True)

    # Future-proof config knobs
    settings = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sanctuary Participant Profile"
        verbose_name_plural = "Sanctuary Participant Profiles"
        indexes = [
            models.Index(fields=["is_participant", "is_eligible"]),
        ]

    def __str__(self):
        return f"SanctuaryParticipation(user={self.user_id}, participant={self.is_participant}, eligible={self.is_eligible})"


# Sanctuary Participant Audit --------------------------------------------------------------
class SanctuaryParticipantAudit(models.Model):
    """
    Append-only audit log for participation/eligibility changes.
    """
    ACTION_OPT_IN = "opt_in"
    ACTION_OPT_OUT = "opt_out"
    ACTION_ELIGIBLE_TRUE = "eligible_true"
    ACTION_ELIGIBLE_FALSE = "eligible_false"

    ACTION_CHOICES = [
        (ACTION_OPT_IN, "Opt-in"),
        (ACTION_OPT_OUT, "Opt-out"),
        (ACTION_ELIGIBLE_TRUE, "Eligible True"),
        (ACTION_ELIGIBLE_FALSE, "Eligible False"),
    ]

    profile = models.ForeignKey(
        SanctuaryParticipantProfile,
        on_delete=models.CASCADE,
        related_name="audits",
    )

    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sanctuary_participant_audits",
        help_text="Admin/system actor (nullable for user self-actions).",
    )
    reason = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sanctuary Participant Audit"
        verbose_name_plural = "Sanctuary Participant Audits"
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action"]),
        ]

    def clean(self):
        # Enforce reason when blocking eligibility
        if self.action == self.ACTION_ELIGIBLE_FALSE and not (self.reason or "").strip():
            from django.core.exceptions import ValidationError
            raise ValidationError({"reason": "Reason is required when setting eligible to False."})

    def __str__(self):
        return f"Audit(profile={self.profile_id}, action={self.action}, at={self.created_at})"
    

# SANCTUARY REQUEST Model ----------------------------------------------------------------
class SanctuaryRequest(models.Model):
    id = models.BigAutoField(primary_key=True)

    # Target type (content, account, organization, messenger_group)
    request_type = models.CharField(
        max_length=32,
        choices=REQUEST_TYPE_CHOICES,
        verbose_name="Request Type",
    )

    # Multiple reasons allowed (stored as list of reason codes)
    reasons = models.JSONField(
        default=list,
        verbose_name="Reported Reasons",
        help_text="List of selected violation reasons",
    )

    # Optional user explanation
    description = models.TextField(
        null=True,
        blank=True,
        verbose_name="Additional Description",
    )

    # Current lifecycle state
    status = models.CharField(
        max_length=32,
        choices=REQUEST_STATUS_CHOICES,
        default=PENDING,
        verbose_name="Request Status",
    )

    # Snapshot of report count at creation time
    report_count_snapshot = models.PositiveIntegerField(
        default=1,
        verbose_name="Report Count Snapshot",
        help_text="Report count when this request was created",
    )

    # Whether this case is council-based, admin-only, or monitor-only
    resolution_mode = models.CharField(
        max_length=32,
        choices=[
            ('monitor', 'Monitor Only'),
            ('council', 'Council Review'),
            ('admin', 'Admin Review'),
        ],
        default='monitor',
        verbose_name="Resolution Mode",
    )

    # Tradition-specific protection flag
    tradition_protected = models.BooleanField(
        default=False,
        verbose_name="Tradition-Specific Perspective",
        help_text="Marks content as protected under tradition-specific theological perspective",
    )

    # Audit label for protected content
    tradition_label = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        verbose_name="Tradition Label",
        help_text="e.g. Tradition-Specific Perspective",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated",
    )

    # Requester
    requester = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sanctuary_requests",
        verbose_name="Requester",
    )

    # Assigned admin (if admin flow)
    assigned_admin = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_sanctuary_requests",
        limit_choices_to={'is_staff': True},
        verbose_name="Assigned Admin",
    )

    admin_assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Admin Assigned At",
    )

    # Generic target (content / account / org / group)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey( 'content_type', 'object_id')

    class Meta:
        ordering = ["-created_at"]
        unique_together = (
            ("requester", "content_type", "object_id"),
        )
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "resolution_mode"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Sanctuary Request"
        verbose_name_plural = "Sanctuary Requests"

    def __str__(self):
        return f"SanctuaryRequest({self.request_type}) by {self.requester_id}"


# SANCTUARY REVIEW Model --------------------------------------------------------------------------
class SanctuaryReview(models.Model):
    """
    A single council member's vote on a Sanctuary request.
    """

    id = models.BigAutoField(primary_key=True)

    sanctuary_request = models.ForeignKey(
        SanctuaryRequest,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Sanctuary Request",
    )

    reviewer = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="sanctuary_reviews",
        verbose_name="Reviewer",
    )

    # Vote status
    review_status = models.CharField(
        max_length=32,
        choices=[
            ('no_opinion', 'No Opinion'),
            ('violation_confirmed', 'Violation Confirmed'),
            ('violation_rejected', 'Violation Rejected'),
        ],
        default='no_opinion',
        verbose_name="Review Status",
    )

    # Optional reviewer comment
    comment = models.TextField(
        null=True,
        blank=True,
        verbose_name="Reviewer Comment",
    )

    # Council metadata
    is_primary_tradition_match = models.BooleanField(
        default=False,
        verbose_name="Primary Tradition Match",
        help_text="True if reviewer shares tradition with reported target",
    )

    is_active = models.BooleanField(default=True)  # Active council slot
    replaced_at = models.DateTimeField(null=True, blank=True)  # Audit
    reminded_at = models.DateTimeField(null=True, blank=True)  # Optional

    assigned_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Assigned At",
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Reviewed At",
    )

    class Meta:
        unique_together = (
            ('sanctuary_request', 'reviewer'),
        )
        verbose_name = "Sanctuary Review"
        verbose_name_plural = "Sanctuary Reviews"

    def __str__(self):
        return f"Review({self.review_status}) by {self.reviewer_id}"



# SANCTUARY OUTCOME Model --------------------------------------------------------------------
class SanctuaryOutcome(models.Model):
    """
    Final decision of a Sanctuary process.
    """

    id = models.BigAutoField(primary_key=True)

    # Outcome result
    outcome_status = models.CharField(
        max_length=32,
        choices=[
            ('outcome_confirmed', 'Confirmed'),
            ('outcome_rejected', 'Rejected'),
            ('outcome_pending', 'Pending'),
        ],
        default='outcome_pending',
        verbose_name="Outcome Status",
    )

    # Linked requests
    sanctuary_requests = models.ManyToManyField(
        SanctuaryRequest,
        related_name="outcomes",
        verbose_name="Related Sanctuary Requests",
    )

    # Generic target
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Whether outcome grants tradition-based protection
    tradition_protection_granted = models.BooleanField(
        default=False,
        verbose_name="Tradition Protection Granted",
    )

    tradition_protection_note = models.TextField(
        null=True,
        blank=True,
        verbose_name="Tradition Protection Note",
        help_text="Explanation for Tradition-Specific Perspective",
    )

    # Appeal fields
    is_appealed = models.BooleanField(
        default=False,
        verbose_name="Is Appealed",
    )

    appeal_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Appeal Message",
    )

    appeal_deadline = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Appeal Deadline",
    )

    # Admin handling appeal
    assigned_admin = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sanctuary_outcome_appeals",
        verbose_name="Appeal Admin",
    )

    admin_assigned_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Appeal Admin Assigned At"
    )

    admin_reviewed = models.BooleanField(
        default=False,
        verbose_name="Admin Reviewed Appeal",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At",
    )

    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Finalized At",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["is_appealed", "admin_reviewed"]),
            models.Index(fields=["appeal_deadline"]),
        ]
        verbose_name = "Sanctuary Outcome"
        verbose_name_plural = "Sanctuary Outcomes"

    def __str__(self):
        return f"SanctuaryOutcome({self.outcome_status})"


# SANCTUARY PROTECTION LABEL Model ----------------------------------------------------------------
class SanctuaryProtectionLabel(models.Model):
    """
    Generic protection/label for any target (content/account/org/group).
    Used to prevent repeated Sanctuary weaponization.
    """

    # Label types
    TRADITION_SPECIFIC_PERSPECTIVE = "tradition_specific_perspective"

    LABEL_CHOICES = [
        (TRADITION_SPECIFIC_PERSPECTIVE, "Tradition-Specific Perspective"),
    ]

    # Who applied it
    APPLIED_BY_COUNCIL = "council"
    APPLIED_BY_ADMIN = "admin"
    APPLIED_BY_SYSTEM = "system"

    APPLIED_BY_CHOICES = [
        (APPLIED_BY_COUNCIL, "Council"),
        (APPLIED_BY_ADMIN, "Admin"),
        (APPLIED_BY_SYSTEM, "System"),
    ]

    id = models.BigAutoField(primary_key=True)

    # Generic target
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    label_type = models.CharField(max_length=64, choices=LABEL_CHOICES)
    applied_by = models.CharField(max_length=16, choices=APPLIED_BY_CHOICES, default=APPLIED_BY_SYSTEM)

    # Optional linkage to outcome (auditability)
    outcome = models.ForeignKey(
        "sanctuary.SanctuaryOutcome",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="protection_labels",
    )

    # Optional note for admins/council reasoning
    note = models.TextField(null=True, blank=True)

    # Time controls
    is_active = models.BooleanField(default=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # Null = no expiry

    # Who created it
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_sanctuary_labels",
    )

    class Meta:
        # One active label of same type per target
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "label_type", "is_active"],
                name="uniq_active_label_per_target_type",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["label_type", "is_active"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        """Return True if expires_at passed."""
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def __str__(self):
        return f"{self.label_type} on {self.content_type_id}:{self.object_id} (active={self.is_active})"