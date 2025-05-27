from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.sanctuary.constants import (
                                        POST_REPORT_CHOICES, ACCOUNT_REPORT_CHOICES,
                                        REQUEST_TYPE_CHOICES, REQUEST_STATUS_CHOICES,
                                        POST_REQUEST, ACCOUNT_REQUEST, PENDING,
                                        REVIEW_STATUS_CHOICES, NO_OPINION, OUTCOME_CHOICES
                                    )
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


# SANCTUARY REQUSE Model -----------------------------------------------------------------------------------------------------------
class SanctuaryRequest(models.Model):
    id = models.BigAutoField(primary_key=True)
    request_type = models.CharField(max_length=50, choices=REQUEST_TYPE_CHOICES, verbose_name="Request Type")
    reason = models.CharField(max_length=255, verbose_name="Request Reason")
    description = models.TextField(null=True, blank=True, verbose_name="Description")
    status = models.CharField(max_length=50, choices=REQUEST_STATUS_CHOICES, default=PENDING, verbose_name="Status")
    request_date = models.DateTimeField(auto_now_add=True, verbose_name="Request Date")
    requester = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sanctuary_requests', verbose_name="Requester")
    assigned_admin = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sanctuary_requests', limit_choices_to={'is_staff': True}, verbose_name="Assigned Admin")
    admin_assigned_at = models.DateTimeField(null=True, blank=True, verbose_name="Admin Assigned At")  # زمان اختصاص ادمین

    # Fields for Generic Relation to connect to any model (Post, Account, Organization, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.request_type == POST_REQUEST and self.reason not in dict(POST_REPORT_CHOICES).keys():
            raise ValidationError("Invalid reason for post report.")
        elif self.request_type == ACCOUNT_REQUEST and self.reason not in dict(ACCOUNT_REPORT_CHOICES).keys():
            raise ValidationError("Invalid reason for account report.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sanctuary Request by {self.requester} - {self.request_type}"


# SANCTUARY REVIEW Model ------------------------------------------------------------------------------------------------------------
class SanctuaryReview(models.Model):
    id = models.BigAutoField(primary_key=True)
    sanctuary_request = models.ForeignKey('SanctuaryRequest', on_delete=models.CASCADE, related_name='reviews', verbose_name="Sanctuary Request")
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sanctuary_reviews', verbose_name="Reviewer")
    review_status = models.CharField(max_length=50, choices=REVIEW_STATUS_CHOICES, default=NO_OPINION, verbose_name="Review Status")
    comment = models.TextField(null=True, blank=True, verbose_name="Comment")
    review_date = models.DateTimeField(auto_now_add=True, verbose_name="Review Date")
    assigned_at = models.DateTimeField(auto_now_add=True, verbose_name="Assigned At")

    def __str__(self):
        return f"Review by {self.reviewer.username} on {self.sanctuary_request.request_type}"



# SANCTUARY OUTCOME Model ------------------------------------------------------------------------------------------------------------
class SanctuaryOutcome(models.Model):
    id = models.BigAutoField(primary_key=True)
    outcome_status = models.CharField(max_length=50, choices=OUTCOME_CHOICES, verbose_name="Outcome Status")
    completion_date = models.DateTimeField(auto_now_add=True, verbose_name="Completion Date")
    sanctuary_requests = models.ManyToManyField('SanctuaryRequest', related_name='outcomes', verbose_name="Sanctuary Requests")
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, verbose_name="Content Type")
    object_id = models.PositiveIntegerField(verbose_name="Object ID")
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Appeal Fields
    is_appealed = models.BooleanField(default=False, verbose_name="Is Appealed")
    admin_reviewed = models.BooleanField(default=False, verbose_name="Admin Reviewed")
    assigned_admin = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_sanctuary_outcome_appeals')
    admin_assigned_at = models.DateTimeField(null=True, blank=True, verbose_name="Admin Assigned At")
    appeal_message = models.TextField(null=True, blank=True, verbose_name="Appeal Message")
    appeal_deadline = models.DateTimeField(null=True, blank=True, verbose_name="Appeal Deadline")

    def __str__(self):
        return f"Outcome for {self.content_object} - {self.outcome_status}"