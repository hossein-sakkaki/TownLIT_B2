# apps/audio_catalog/admin/forms.py

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from apps.audio_catalog.models import (
    MusicArtwork,
    MusicRightsRecord,
    MusicTrack,
    MusicTrackVariant,
)


MILLISECONDS = Decimal("1000")


def _seconds_to_ms(value: Decimal) -> int:
    return int(
        (value * MILLISECONDS).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _ms_to_seconds(
    value: int | None,
) -> Decimal | None:
    if value is None:
        return None

    return (
        Decimal(value)
        / MILLISECONDS
    ).quantize(
        Decimal("0.001")
    )


class MusicTrackAdminForm(forms.ModelForm):
    """
    Human-friendly form for the main music workflow.

    The database continues to store milliseconds, while admins
    work with seconds.
    """

    duration_seconds = forms.DecimalField(
        label="Track duration (seconds)",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        help_text=(
            "Enter the full duration in seconds. "
            "Example: 3 minutes 12 seconds = 192."
        ),
    )

    min_clip_seconds = forms.DecimalField(
        label="Minimum clip (seconds)",
        min_value=Decimal("0.001"),
        max_digits=8,
        decimal_places=3,
        initial=Decimal("5"),
        help_text=(
            "Shortest music clip a user may select."
        ),
    )

    max_clip_seconds = forms.DecimalField(
        label="Maximum clip (seconds)",
        min_value=Decimal("0.001"),
        max_digits=8,
        decimal_places=3,
        initial=Decimal("60"),
        help_text=(
            "Longest music clip a user may select."
        ),
    )

    class Meta:
        model = MusicTrack

        exclude = (
            "duration_ms",
            "min_clip_duration_ms",
            "max_clip_duration_ms",
        )

        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 4,
                }
            ),
            "metadata": forms.Textarea(
                attrs={
                    "rows": 5,
                }
            ),
            "search_document": forms.Textarea(
                attrs={
                    "rows": 4,
                }
            ),
        }

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        if (
            self.instance
            and self.instance.pk
        ):
            self.fields[
                "duration_seconds"
            ].initial = _ms_to_seconds(
                self.instance.duration_ms
            )

            self.fields[
                "min_clip_seconds"
            ].initial = _ms_to_seconds(
                self.instance.min_clip_duration_ms
            )

            self.fields[
                "max_clip_seconds"
            ].initial = _ms_to_seconds(
                self.instance.max_clip_duration_ms
            )

        self.fields[
            "catalog"
        ].help_text = (
            "Choose where this track belongs. "
            "For TownLIT-owned music, normally use "
            "TownLIT Originals or TownLIT AI Originals."
        )

        self.fields[
            "source_type"
        ].help_text = (
            "How TownLIT obtained or created this track."
        )

        self.fields[
            "is_test_asset"
        ].help_text = (
            "Test assets are never available to normal users."
        )

        self.fields[
            "allow_standalone_download"
        ].help_text = (
            "Normally keep this disabled."
        )

        self.fields[
            "allow_external_export"
        ].help_text = (
            "Enable only when the music rights explicitly "
            "permit export outside TownLIT."
        )

    def clean(self):
        cleaned = super().clean()

        minimum = cleaned.get(
            "min_clip_seconds"
        )

        maximum = cleaned.get(
            "max_clip_seconds"
        )

        if (
            minimum is not None
            and maximum is not None
            and maximum < minimum
        ):
            raise ValidationError(
                "Maximum clip duration cannot be shorter "
                "than the minimum clip duration."
            )

        if (
            cleaned.get(
                "is_instrumental"
            )
            and cleaned.get(
                "has_vocals"
            )
        ):
            raise ValidationError(
                "An instrumental track cannot also be marked "
                "as having vocals."
            )

        if (
            cleaned.get(
                "source_type"
            )
            == MusicTrack.SourceType.TOWNLIT_AI_ASSISTED
        ):
            cleaned[
                "is_ai_assisted"
            ] = True

        return cleaned

    def save(
        self,
        commit=True,
    ):
        instance = super().save(
            commit=False
        )

        instance.duration_ms = (
            _seconds_to_ms(
                self.cleaned_data[
                    "duration_seconds"
                ]
            )
        )

        instance.min_clip_duration_ms = (
            _seconds_to_ms(
                self.cleaned_data[
                    "min_clip_seconds"
                ]
            )
        )

        instance.max_clip_duration_ms = (
            _seconds_to_ms(
                self.cleaned_data[
                    "max_clip_seconds"
                ]
            )
        )

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class MusicArtworkInlineForm(
    forms.ModelForm
):
    class Meta:
        model = MusicArtwork
        fields = "__all__"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        if not self.instance.pk:
            self.fields[
                "role"
            ].initial = (
                MusicArtwork.Role.PRIMARY
            )

            self.fields[
                "is_active"
            ].initial = True


class MusicTrackVariantInlineForm(
    forms.ModelForm
):
    class Meta:
        model = MusicTrackVariant
        fields = "__all__"

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        if not self.instance.pk:
            self.fields[
                "variant_type"
            ].initial = (
                MusicTrackVariant
                .VariantType
                .PLAYBACK
            )

            self.fields[
                "is_streamable"
            ].initial = True

            self.fields[
                "is_active"
            ].initial = True


class MusicRightsRecordInlineForm(
    forms.ModelForm
):
    """
    Adds a convenience preset without changing the legal model.
    """

    apply_townlit_usage_preset = (
        forms.BooleanField(
            required=False,
            label=(
                "Apply TownLIT in-app usage preset"
            ),
            help_text=(
                "Check this only after confirming that the "
                "license permits UGC use, streaming, "
                "synchronization, clipping, hosting, and "
                "sublicensing to TownLIT end users. "
                "This does NOT automatically mark the rights "
                "record as Cleared."
            ),
        )
    )

    class Meta:
        model = MusicRightsRecord
        fields = "__all__"

    def save(
        self,
        commit=True,
    ):
        instance = super().save(
            commit=False
        )

        if self.cleaned_data.get(
            "apply_townlit_usage_preset"
        ):
            instance.ugc_use_allowed = True
            instance.streaming_allowed = True
            instance.synchronization_allowed = True
            instance.clipping_allowed = True
            instance.hosting_allowed = True

            instance.sublicensing_to_end_users_allowed = (
                True
            )

        if commit:
            instance.save()
            self.save_m2m()

        return instance


def _meaningful_inline_forms(
    formset,
):
    for form in formset.forms:
        cleaned = getattr(
            form,
            "cleaned_data",
            None,
        )

        if not cleaned:
            continue

        if cleaned.get(
            "DELETE"
        ):
            continue

        if (
            form.instance.pk
            or form.has_changed()
        ):
            yield form


class SinglePrimaryArtworkFormSet(
    BaseInlineFormSet
):
    """
    Ensures one active primary artwork.

    If artwork exists but no primary was explicitly selected,
    the first active artwork automatically becomes primary.
    """

    def clean(self):
        super().clean()

        if any(
            self.errors
        ):
            return

        active_forms = []
        selected_forms = []

        for form in _meaningful_inline_forms(
            self
        ):
            cleaned = form.cleaned_data

            is_active = bool(
                cleaned.get(
                    "is_active",
                    True,
                )
            )

            is_primary = bool(
                cleaned.get(
                    "is_primary",
                    False,
                )
            )

            if (
                is_primary
                and not is_active
            ):
                cleaned[
                    "is_primary"
                ] = False

                form.instance.is_primary = False
                is_primary = False

            if is_active:
                active_forms.append(
                    form
                )

            if (
                is_active
                and is_primary
            ):
                selected_forms.append(
                    form
                )

        if len(
            selected_forms
        ) > 1:
            raise ValidationError(
                "Only one active artwork can be primary."
            )

        if (
            not selected_forms
            and active_forms
        ):
            chosen = active_forms[0]

            chosen.cleaned_data[
                "is_primary"
            ] = True

            chosen.instance.is_primary = True


class SingleDefaultVariantFormSet(
    BaseInlineFormSet
):
    """
    Ensures one active default playback variant.

    If the admin uploads playable audio without selecting a
    default, the first active streamable variant becomes default.
    """

    def clean(self):
        super().clean()

        if any(
            self.errors
        ):
            return

        playable_forms = []
        selected_forms = []

        for form in _meaningful_inline_forms(
            self
        ):
            cleaned = form.cleaned_data

            is_active = bool(
                cleaned.get(
                    "is_active",
                    True,
                )
            )

            is_streamable = bool(
                cleaned.get(
                    "is_streamable",
                    True,
                )
            )

            is_default = bool(
                cleaned.get(
                    "is_default",
                    False,
                )
            )

            if (
                is_default
                and (
                    not is_active
                    or not is_streamable
                )
            ):
                cleaned[
                    "is_default"
                ] = False

                form.instance.is_default = False
                is_default = False

            if (
                is_active
                and is_streamable
            ):
                playable_forms.append(
                    form
                )

            if (
                is_active
                and is_streamable
                and is_default
            ):
                selected_forms.append(
                    form
                )

        if len(
            selected_forms
        ) > 1:
            raise ValidationError(
                "Only one active streamable variant can "
                "be the track default."
            )

        if (
            not selected_forms
            and playable_forms
        ):
            chosen = playable_forms[0]

            chosen.cleaned_data[
                "is_default"
            ] = True

            chosen.instance.is_default = True