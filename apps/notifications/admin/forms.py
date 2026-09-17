# apps/notifications/admin/forms.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-04.
# Last Update by Hossein Sakkaki on 2026-09-04.
#

from django import forms

from apps.notifications.models import NotificationCampaign


class NotificationCampaignAdminForm(forms.ModelForm):
    class Meta:
        model = NotificationCampaign
        fields = "__all__"
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Write the user-facing notification message.",
                }
            ),
            "action_url": forms.TextInput(
                attrs={
                    "placeholder": "https://... or /townlit/path/",
                }
            ),
        }

    def clean(self):
        cleaned = super().clean()

        audience = cleaned.get("audience_type")
        selected_users = cleaned.get("selected_users")

        if (
            audience == NotificationCampaign.Audience.SELECTED
            and not selected_users
        ):
            self.add_error(
                "selected_users",
                "Choose at least one recipient.",
            )

        return cleaned