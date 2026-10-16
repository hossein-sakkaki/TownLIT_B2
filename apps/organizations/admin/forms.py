# apps/organizations/admin/forms.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-13.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from django import forms
from django.utils import timezone

from apps.organizations.constants import (
    OrganizationVerificationGrantStatus,
    OrganizationVerificationStatus,
)


class VerificationCaseWorkflowForm(forms.Form):
    ACTION_START_REVIEW = "start_review"
    ACTION_NEEDS_INFORMATION = "needs_information"
    ACTION_APPROVE = "approve"
    ACTION_REJECT = "reject"

    action = forms.ChoiceField(
        label="Action",
        choices=(),
    )
    review_notes = forms.CharField(
        label="Reviewer notes",
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Required when requesting more information "
                    "or rejecting the case."
                ),
            }
        ),
        help_text=(
            "Required for Needs Information and Reject. "
            "Ignored for Start Review and Approve."
        ),
    )
    expires_at = forms.DateTimeField(
        label="Verification expires at",
        required=False,
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        input_formats=(
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ),
        help_text=(
            "Optional for approval. Leave blank for a grant without "
            "a configured expiry."
        ),
    )

    def __init__(self, *args, verification_case, **kwargs):
        super().__init__(*args, **kwargs)
        self.verification_case = verification_case
        self.fields["action"].choices = self.available_actions(
            verification_case
        )

        if verification_case.review_notes:
            self.fields["review_notes"].initial = (
                verification_case.review_notes
            )

    @classmethod
    def available_actions(cls, verification_case):
        status = verification_case.status

        if status == OrganizationVerificationStatus.SUBMITTED:
            return (
                (cls.ACTION_START_REVIEW, "Start review"),
                (
                    cls.ACTION_NEEDS_INFORMATION,
                    "Request more information",
                ),
                (cls.ACTION_APPROVE, "Approve verification"),
                (cls.ACTION_REJECT, "Reject verification"),
            )

        if status == OrganizationVerificationStatus.UNDER_REVIEW:
            return (
                (
                    cls.ACTION_NEEDS_INFORMATION,
                    "Request more information",
                ),
                (cls.ACTION_APPROVE, "Approve verification"),
                (cls.ACTION_REJECT, "Reject verification"),
            )

        if status == OrganizationVerificationStatus.NEEDS_INFORMATION:
            return (
                (cls.ACTION_REJECT, "Reject verification"),
            )

        return ()

    @classmethod
    def has_available_action(cls, verification_case):
        return bool(cls.available_actions(verification_case))

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        review_notes = str(
            cleaned_data.get("review_notes") or ""
        ).strip()
        expires_at = cleaned_data.get("expires_at")

        if action in {
            self.ACTION_NEEDS_INFORMATION,
            self.ACTION_REJECT,
        } and not review_notes:
            self.add_error(
                "review_notes",
                "Reviewer notes are required for this action.",
            )

        if (
            action == self.ACTION_APPROVE
            and expires_at is not None
            and expires_at <= timezone.now()
        ):
            self.add_error(
                "expires_at",
                "Verification expiry must be in the future.",
            )

        cleaned_data["review_notes"] = review_notes or None
        return cleaned_data


class VerificationDocumentWorkflowForm(forms.Form):
    ACTION_ACCEPT = "accept"
    ACTION_REJECT = "reject"

    action = forms.ChoiceField(
        label="Decision",
        choices=(
            (ACTION_ACCEPT, "Accept document"),
            (ACTION_REJECT, "Reject document"),
        ),
    )
    note = forms.CharField(
        label="Reviewer note",
        required=False,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Required when rejecting a document.",
            }
        ),
    )

    def __init__(self, *args, document, **kwargs):
        super().__init__(*args, **kwargs)
        self.document = document

        if document.review_note:
            self.fields["note"].initial = document.review_note

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get("action")
        note = str(
            cleaned_data.get("note") or ""
        ).strip()

        if action == self.ACTION_REJECT and not note:
            self.add_error(
                "note",
                "A reviewer note is required when rejecting a document.",
            )

        cleaned_data["note"] = note or None
        return cleaned_data


class VerificationGrantRevokeForm(forms.Form):
    reason = forms.CharField(
        label="Revocation reason",
        required=True,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "placeholder": (
                    "Explain why this verification grant is being revoked."
                ),
            }
        ),
    )

    def __init__(self, *args, grant, **kwargs):
        super().__init__(*args, **kwargs)
        self.grant = grant

    def clean(self):
        cleaned_data = super().clean()

        if self.grant.status != OrganizationVerificationGrantStatus.ACTIVE:
            raise forms.ValidationError(
                "Only an active verification grant can be revoked."
            )

        return cleaned_data

    def clean_reason(self):
        reason = str(
            self.cleaned_data.get("reason") or ""
        ).strip()

        if not reason:
            raise forms.ValidationError(
                "A revocation reason is required."
            )

        if len(reason) > 1000:
            raise forms.ValidationError(
                "Revocation reason must be 1000 characters or fewer."
            )

        return reason
