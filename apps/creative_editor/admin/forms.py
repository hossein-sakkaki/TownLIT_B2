# apps/creative_editor/admin/forms.py

from __future__ import annotations

import json

from django import forms
from django.core.exceptions import ValidationError

from apps.creative_editor.models import (
    CreativeBackgroundPreset,
)


class CreativeBackgroundPresetAdminForm(
    forms.ModelForm
):
    """
    Visual Admin form for creative backgrounds.
    """

    color = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": (
                    "vTextField "
                    "creative-background-color-input"
                ),
                "placeholder": "#0F52BAFF",
                "autocomplete": "off",
            }
        ),
        help_text=(
            "Solid color using #RRGGBB or #RRGGBBAA."
        ),
    )

    colors = forms.JSONField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": (
                    "vLargeTextField "
                    "creative-background-colors-input"
                ),
                "rows": 7,
                "placeholder": (
                    '[\n'
                    '  "#071A33FF",\n'
                    '  "#0F52BAFF",\n'
                    '  "#F6C860FF"\n'
                    "]"
                ),
                "spellcheck": "false",
            }
        ),
        help_text=(
            "Gradient colors as a JSON array. "
            "Use between two and five colors."
        ),
    )

    supported_consumers = forms.JSONField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "vLargeTextField",
                "rows": 4,
                "placeholder": (
                    '["journey", "moment"]'
                ),
                "spellcheck": "false",
            }
        ),
        help_text=(
            "Empty list means all consumers. "
            "Supported values include journey, moment, "
            "testimony, profile, announcement and custom."
        ),
    )

    metadata = forms.JSONField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "vLargeTextField",
                "rows": 10,
                "spellcheck": "false",
            }
        ),
    )

    class Meta:
        model = CreativeBackgroundPreset

        fields = "__all__"

        widgets = {
            "angle": forms.NumberInput(
                attrs={
                    "min": "-360",
                    "max": "360",
                    "step": "1",
                    "class": (
                        "creative-background-angle-input"
                    ),
                }
            ),
        }

    def clean_color(
        self,
    ) -> str:
        value = str(
            self.cleaned_data.get(
                "color",
                "",
            )
            or ""
        ).strip()

        if not value:
            return ""

        return (
            CreativeBackgroundPreset
            ._normalize_hex(
                value,
            )
        )

    def clean_colors(
        self,
    ) -> list[str]:
        values = (
            self.cleaned_data.get(
                "colors",
            )
            or []
        )

        if not isinstance(
            values,
            list,
        ):
            raise ValidationError(
                "Gradient colors must be a JSON list."
            )

        return [
            CreativeBackgroundPreset
            ._normalize_hex(value)
            for value in values
        ]

    def clean_supported_consumers(
        self,
    ) -> list[str]:
        values = (
            self.cleaned_data.get(
                "supported_consumers",
            )
            or []
        )

        return (
            CreativeBackgroundPreset
            ._normalize_consumers(values)
        )

    def clean_metadata(
        self,
    ) -> dict:
        value = (
            self.cleaned_data.get(
                "metadata",
            )
            or {}
        )

        if not isinstance(
            value,
            dict,
        ):
            raise ValidationError(
                "Metadata must be a JSON object."
            )

        return value

    def clean(
        self,
    ):
        cleaned_data = super().clean()

        background_type = cleaned_data.get(
            "background_type"
        )

        color = cleaned_data.get(
            "color",
            "",
        )

        colors = cleaned_data.get(
            "colors",
            [],
        )

        if (
            background_type
            == CreativeBackgroundPreset
            .BackgroundType
            .COLOR
        ):
            if not color:
                self.add_error(
                    "color",
                    (
                        "A solid background requires "
                        "one color."
                    ),
                )

            cleaned_data["colors"] = []

        elif (
            background_type
            == CreativeBackgroundPreset
            .BackgroundType
            .GRADIENT
        ):
            if len(colors) < 2:
                self.add_error(
                    "colors",
                    (
                        "A gradient requires at least "
                        "two colors."
                    ),
                )

            if len(colors) > 5:
                self.add_error(
                    "colors",
                    (
                        "A gradient cannot exceed "
                        "five colors."
                    ),
                )

            cleaned_data["color"] = ""

        return cleaned_data

    def save(
        self,
        commit: bool = True,
    ):
        instance = super().save(
            commit=False,
        )

        instance.full_clean()

        if commit:
            instance.save()
            self.save_m2m()

        return instance