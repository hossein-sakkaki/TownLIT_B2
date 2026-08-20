# apps/communication/forms/templates.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


import re

from django import forms
from django.core.exceptions import ValidationError

from apps.communication.constants import EmailEditorMode
from apps.communication.models import EmailTemplate, EmailTheme
from utils.email.template_context import validate_template_variables


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class EmailTemplateAdminForm(forms.ModelForm):
    class Meta:
        model = EmailTemplate
        fields = "__all__"
        help_texts = {
            "editor_mode": (
                "Use Block Builder for new admin-created campaign templates. "
                "Rich Text keeps compatibility with existing templates."
            ),
            "default_context": (
                "Advanced defaults only. Most admins should leave this empty."
            ),
        }

    def clean(self):
        cleaned = super().clean()

        editor_mode = cleaned.get("editor_mode")
        body = cleaned.get("body_template") or ""
        subject = cleaned.get("subject_template") or ""
        preheader = cleaned.get("preheader_template") or ""

        for value, field_name in (
            (subject, "subject_template"),
            (preheader, "preheader_template"),
            (body, "body_template"),
        ):
            if not value:
                continue

            try:
                validate_template_variables(value)
            except ValueError as error:
                self.add_error(
                    field_name,
                    f"Invalid template variable: {error}",
                )

        if editor_mode == EmailEditorMode.HTML and not body:
            self.add_error(
                "body_template",
                "Custom HTML templates need body content.",
            )

        return cleaned


class EmailThemeAdminForm(forms.ModelForm):
    class Meta:
        model = EmailTheme
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        color_fields = [
            "background_color",
            "surface_color",
            "text_color",
            "heading_color",
            "accent_color",
            "secondary_accent_color",
            "muted_color",
            "button_text_color",
        ]

        for field_name in color_fields:
            value = cleaned.get(field_name)

            if value and not HEX_COLOR_RE.match(value):
                self.add_error(
                    field_name,
                    "Use a six-digit HEX color such as #0F52BA.",
                )

        return cleaned