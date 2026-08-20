# apps/communication/forms/audiences.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django import forms

from apps.communication.constants import (
    AudienceKind,
    AudienceRuleField,
    AudienceRuleOperator,
)
from apps.communication.models import EmailAudience, EmailAudienceRule


SUPPORTED_RULE_FIELDS = [
    AudienceRuleField.ACTIVE,
    AudienceRuleField.MEMBER,
    AudienceRuleField.ADMIN,
    AudienceRuleField.SUSPENDED,
    AudienceRuleField.LABEL,
    AudienceRuleField.REGISTER_DATE,
]


class EmailAudienceAdminForm(forms.ModelForm):
    class Meta:
        model = EmailAudience
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        kind = cleaned.get("kind")
        preset_key = cleaned.get("preset_key")

        if kind == AudienceKind.PRESET and not preset_key:
            self.add_error(
                "preset_key",
                "Preset audiences need a TownLIT preset.",
            )

        if kind != AudienceKind.PRESET and preset_key:
            self.add_error(
                "preset_key",
                "Only Preset audiences should use a preset key.",
            )

        return cleaned


class EmailAudienceRuleAdminForm(forms.ModelForm):
    rule_value = forms.CharField(
        required=False,
        label="Value",
        help_text=(
            "For 'Is One Of', enter comma-separated values. "
            "True/False rules do not need a value."
        ),
    )

    class Meta:
        model = EmailAudienceRule
        exclude = ["value"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["field"].choices = [
            (value, AudienceRuleField(value).label)
            for value in SUPPORTED_RULE_FIELDS
        ]

        if self.instance and self.instance.pk:
            value = self.instance.value

            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            elif value is not None:
                value = str(value)
            else:
                value = ""

            self.fields["rule_value"].initial = value

    def clean(self):
        cleaned = super().clean()

        operator = cleaned.get("operator")
        raw_value = (cleaned.get("rule_value") or "").strip()

        if operator in {
            AudienceRuleOperator.TRUE,
            AudienceRuleOperator.FALSE,
        }:
            self.instance.value = None
            return cleaned

        if not raw_value:
            self.add_error(
                "rule_value",
                "This operator requires a value.",
            )
            return cleaned

        if operator in {
            AudienceRuleOperator.IN,
            AudienceRuleOperator.NOT_IN,
        }:
            self.instance.value = [
                value.strip()
                for value in raw_value.split(",")
                if value.strip()
            ]
        else:
            self.instance.value = raw_value

        return cleaned