from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import SanctuaryParticipantProfile


# USER Form ----------------------------------------------------------------------
class SanctuaryParticipantProfileAdminForm(forms.ModelForm):
    """
    Enforce reason when blocking eligibility from admin UI.
    """
    class Meta:
        model = SanctuaryParticipantProfile
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        is_eligible = cleaned.get("is_eligible")
        reason = (cleaned.get("eligible_reason") or "").strip()

        # Require reason when setting eligible=False
        if is_eligible is False and not reason:
            raise ValidationError({"eligible_reason": "Reason is required when setting eligible to False."})
        return cleaned
