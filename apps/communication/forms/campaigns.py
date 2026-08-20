# apps/communication/forms/campaigns.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.contrib.admin.widgets import (
    AutocompleteSelect,
    AutocompleteSelectMultiple,
)
from django.utils import timezone
from django.utils.safestring import mark_safe

from apps.communication.models import EmailCampaign
from utils.email.template_context import ALLOWED_TEMPLATE_VARIABLES
from apps.communication.services.html_safety import (
    EmailHTMLSafetyService,
)

TIMEZONE_CHOICES = [
    ("America/Vancouver", "Vancouver / Pacific Time"),
    ("America/Toronto", "Toronto / Eastern Time"),
    ("America/Edmonton", "Edmonton / Mountain Time"),
    ("America/Winnipeg", "Winnipeg / Central Time"),
    ("UTC", "UTC"),
]


class EmailCampaignAdminForm(forms.ModelForm):
    schedule_timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        initial="America/Vancouver",
        label="Scheduling Time Zone",
    )

    class Meta:
        model = EmailCampaign
        fields = "__all__"
        widgets = {
            "scheduled_time": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
        }
        help_texts = {
            "title": "Internal campaign name. Recipients do not see this.",
            "subject": "The subject line recipients will see.",
            "preheader_text": (
                "Short preview text shown beside the subject in many inboxes."
            ),
            "template": (
                "Optional reusable design/content template. Campaign blocks "
                "or custom content can override its body."
            ),
            "audience": "Choose a saved audience for reusable targeting.",
            "recipients": (
                "Use this only for a small manual recipient list. Manual "
                "recipients take priority over saved audiences and presets."
            ),
            "target_group": (
                "Quick TownLIT audience preset used when no manual recipients "
                "or saved audience are selected."
            ),
            "ignore_unsubscribe": (
                "Use only for required legal, safety, security, or operational "
                "communication."
            ),
            "custom_html": mark_safe(
                "Legacy/rich-text campaign content. For new campaigns, prefer "
                "Content Blocks.<br><br><strong>Available variables:</strong> "
                + ", ".join(
                    f"<code>{{{{ {name} }}}}</code>"
                    for name in ALLOWED_TEMPLATE_VARIABLES
                )
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["scheduled_time"].input_formats = [
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S",
        ]

    def clean(self):
        cleaned = super().clean()

        recipients = cleaned.get("recipients")
        audience = cleaned.get("audience")

        if recipients and audience:
            raise forms.ValidationError(
                "Choose either Specific Recipients or a Saved Audience, "
                "not both."
            )

        self._normalize_scheduled_time(cleaned)

        scheduled_time = cleaned.get("scheduled_time")

        if (
            scheduled_time
            and self.instance
            and not self.instance.sent_at
            and scheduled_time <= timezone.now()
        ):
            self.add_error(
                "scheduled_time",
                "Scheduled send time must be in the future.",
            )

        return cleaned

    def clean_custom_html(self):
        return (
            EmailHTMLSafetyService
            .sanitize_custom_html(
                self.cleaned_data.get(
                    "custom_html"
                )
            )
        )
        
    def _normalize_scheduled_time(self, cleaned):
        if not self.is_bound:
            return

        raw_value = (self.data.get("scheduled_time") or "").strip()

        if not raw_value:
            return

        timezone_name = (
            cleaned.get("schedule_timezone")
            or "America/Vancouver"
        )

        try:
            selected_timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            self.add_error(
                "schedule_timezone",
                "Unknown scheduling time zone.",
            )
            return

        try:
            parsed = datetime.fromisoformat(raw_value)
        except ValueError:
            return

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=selected_timezone
            )
        else:
            parsed = parsed.astimezone(
                selected_timezone
            )

        cleaned["scheduled_time"] = parsed


class CampaignWorkspaceForm(EmailCampaignAdminForm):
    """
    Friendly campaign form used by the Communication Workspace.
    """

    class Meta(EmailCampaignAdminForm.Meta):
        fields = (
            "title",
            "description",
            "campaign_type",
            "tag",
            "subject",
            "preheader_text",
            "template",
            "theme",
            "audience",
            "recipients",
            "target_group",
            "topic",
            "ignore_unsubscribe",
            "test_email",
            "scheduled_time",
            "schedule_timezone",
            "from_name",
            "reply_to_email",
            "track_opens",
            "track_clicks",
            "utm_source",
            "utm_medium",
            "utm_campaign",
        )

    def __init__(self, *args, admin_site=None, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["schedule_timezone"].initial = (
                "America/Vancouver"
            )

        if admin_site:
            self._configure_autocomplete_widgets(
                admin_site
            )

        self._configure_labels()
        self._lock_terminal_campaign()

    def _configure_autocomplete_widgets(self, admin_site):
        campaign_model = self._meta.model

        recipients_form_field = self.fields["recipients"]
        recipients_model_field = campaign_model._meta.get_field(
            "recipients"
        )

        recipients_widget = AutocompleteSelectMultiple(
            recipients_model_field,
            admin_site,
            attrs={
                **recipients_form_field.widget.attrs,
                "style": "width: 100%;",
                "data-width": "100%",
            },
        )
        recipients_widget.choices = (
            recipients_form_field.choices
        )
        recipients_form_field.widget = recipients_widget

        for field_name in (
            "template",
            "theme",
            "audience",
            "topic",
        ):
            form_field = self.fields[field_name]
            model_field = campaign_model._meta.get_field(
                field_name
            )

            widget = AutocompleteSelect(
                model_field,
                admin_site,
                attrs={
                    **form_field.widget.attrs,
                    "style": "width: 100%;",
                    "data-width": "100%",
                },
            )
            widget.choices = form_field.choices
            form_field.widget = widget

    def _configure_labels(self):
        self.fields["target_group"].label = (
            "Quick TownLIT Group"
        )
        self.fields["recipients"].label = (
            "Specific Recipients"
        )
        self.fields["audience"].label = (
            "Saved Audience"
        )
        self.fields["template"].label = (
            "Email Template"
        )
        self.fields["theme"].label = (
            "Visual Theme"
        )

    def _lock_terminal_campaign(self):
        if not self.instance.pk:
            return

        if self.instance.can_edit_content:
            return

        editable_after_send = {
            "test_email",
        }

        for field_name, field in self.fields.items():
            if field_name not in editable_after_send:
                field.disabled = True