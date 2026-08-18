# apps/audio_catalog/admin/forms.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-03.
# Last Update by Hossein Sakkaki on 2026-08-17.

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.models import BaseInlineFormSet

from apps.audio_catalog.models import (
    AudioContributor,
    MusicArtwork,
    MusicRightsRecord,
    MusicTrack,
    MusicTrackVariant,
    TrackContributor,
)


MILLISECONDS = Decimal("1000")


def _seconds_to_ms(value: Decimal) -> int:
    return int(
        (value * MILLISECONDS).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def _ms_to_seconds(value: int | None) -> Decimal | None:
    if value is None:
        return None

    return (Decimal(value) / MILLISECONDS).quantize(Decimal("0.001"))


# -------------------------------------------------
# Music track
# -------------------------------------------------


class MusicTrackAdminForm(forms.ModelForm):
    """
    Human-friendly track form.

    Database values remain milliseconds while admins work in seconds.
    """

    duration_seconds = forms.DecimalField(
        label="Track duration (seconds)",
        min_value=Decimal("0.001"),
        max_digits=10,
        decimal_places=3,
        help_text="Example: 3 minutes 12 seconds = 192.",
    )

    min_clip_seconds = forms.DecimalField(
        label="Minimum clip (seconds)",
        min_value=Decimal("0.001"),
        max_digits=8,
        decimal_places=3,
        initial=Decimal("5"),
        help_text="Shortest clip a TownLIT user may select.",
    )

    max_clip_seconds = forms.DecimalField(
        label="Maximum clip (seconds)",
        min_value=Decimal("0.001"),
        max_digits=8,
        decimal_places=3,
        initial=Decimal("60"),
        help_text="Longest clip a TownLIT user may select.",
    )

    class Meta:
        model = MusicTrack
        exclude = (
            "duration_ms",
            "min_clip_duration_ms",
            "max_clip_duration_ms",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "metadata": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            self.fields["duration_seconds"].initial = _ms_to_seconds(
                self.instance.duration_ms
            )
            self.fields["min_clip_seconds"].initial = _ms_to_seconds(
                self.instance.min_clip_duration_ms
            )
            self.fields["max_clip_seconds"].initial = _ms_to_seconds(
                self.instance.max_clip_duration_ms
            )

        self.fields["catalog"].help_text = (
            "For TownLIT-owned music, normally use TownLIT Originals "
            "or TownLIT AI Originals."
        )
        self.fields["source_type"].help_text = (
            "How TownLIT obtained or created this track."
        )
        self.fields["is_test_asset"].help_text = (
            "Test assets are never available to normal users."
        )
        self.fields["allow_standalone_download"].help_text = (
            "Normally keep this disabled."
        )
        self.fields["allow_external_export"].help_text = (
            "Enable only when the applicable music rights explicitly "
            "permit external export."
        )

    def clean(self):
        cleaned = super().clean()

        duration = cleaned.get("duration_seconds")
        minimum = cleaned.get("min_clip_seconds")
        maximum = cleaned.get("max_clip_seconds")

        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValidationError(
                "Maximum clip duration cannot be shorter than "
                "the minimum clip duration."
            )

        if duration is not None and minimum is not None and minimum > duration:
            raise ValidationError(
                "Minimum clip duration cannot exceed the full track duration."
            )

        if duration is not None and maximum is not None and maximum > duration:
            raise ValidationError(
                "Maximum clip duration cannot exceed the full track duration."
            )

        if cleaned.get("is_instrumental") and cleaned.get("has_vocals"):
            raise ValidationError(
                "An instrumental track cannot also be marked as having vocals."
            )

        cleaned["is_ai_assisted"] = (
            cleaned.get("source_type")
            == MusicTrack.SourceType.TOWNLIT_AI_ASSISTED
        )

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)

        instance.duration_ms = _seconds_to_ms(
            self.cleaned_data["duration_seconds"]
        )
        instance.min_clip_duration_ms = _seconds_to_ms(
            self.cleaned_data["min_clip_seconds"]
        )
        instance.max_clip_duration_ms = _seconds_to_ms(
            self.cleaned_data["max_clip_seconds"]
        )

        if commit:
            instance.save()
            self.save_m2m()

        return instance


# -------------------------------------------------
# Artwork
# -------------------------------------------------


class MusicArtworkInlineForm(forms.ModelForm):
    class Meta:
        model = MusicArtwork
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["role"].initial = MusicArtwork.Role.PRIMARY
            self.fields["is_active"].initial = True


# -------------------------------------------------
# Audio variant
# -------------------------------------------------


class MusicTrackVariantInlineForm(forms.ModelForm):
    class Meta:
        model = MusicTrackVariant
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields["variant_type"].initial = (
                MusicTrackVariant.VariantType.PLAYBACK
            )
            self.fields["is_streamable"].initial = True
            self.fields["is_active"].initial = True


# -------------------------------------------------
# Rights
# -------------------------------------------------


class MusicRightsRecordInlineForm(forms.ModelForm):
    """
    Adds a convenience preset without changing the legal model.
    """

    apply_townlit_usage_preset = forms.BooleanField(
        required=False,
        label="Apply TownLIT in-app usage preset",
        help_text=(
            "Use only after confirming that the license permits UGC, "
            "streaming, synchronization, clipping, hosting and "
            "sublicensing to TownLIT end users. This does not mark "
            "the record Cleared automatically."
        ),
    )

    class Meta:
        model = MusicRightsRecord
        fields = "__all__"

    def save(self, commit=True):
        instance = super().save(commit=False)

        if self.cleaned_data.get("apply_townlit_usage_preset"):
            instance.ugc_use_allowed = True
            instance.streaming_allowed = True
            instance.synchronization_allowed = True
            instance.clipping_allowed = True
            instance.hosting_allowed = True
            instance.sublicensing_to_end_users_allowed = True

        if commit:
            instance.save()
            self.save_m2m()

        return instance


# -------------------------------------------------
# Shared inline helpers
# -------------------------------------------------


def _meaningful_inline_forms(formset):
    for form in formset.forms:
        cleaned = getattr(form, "cleaned_data", None)

        if not cleaned or cleaned.get("DELETE"):
            continue

        if form.instance.pk or form.has_changed():
            yield form


class SinglePrimaryArtworkFormSet(BaseInlineFormSet):
    """
    Guarantee at most one active primary artwork.

    If artwork exists and no primary is selected, the first active
    artwork automatically becomes primary.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        active_forms = []
        selected_forms = []

        for form in _meaningful_inline_forms(self):
            cleaned = form.cleaned_data
            is_active = bool(cleaned.get("is_active", True))
            is_primary = bool(cleaned.get("is_primary", False))

            if is_primary and not is_active:
                cleaned["is_primary"] = False
                form.instance.is_primary = False
                is_primary = False

            if is_active:
                active_forms.append(form)

            if is_active and is_primary:
                selected_forms.append(form)

        if len(selected_forms) > 1:
            raise ValidationError(
                "Only one active artwork can be primary."
            )

        if not selected_forms and active_forms:
            chosen = active_forms[0]
            chosen.cleaned_data["is_primary"] = True
            chosen.instance.is_primary = True


class SingleDefaultVariantFormSet(BaseInlineFormSet):
    """
    Guarantee at most one active default playback variant.

    If no default is selected, the first active streamable variant
    automatically becomes the default.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        playable_forms = []
        selected_forms = []

        for form in _meaningful_inline_forms(self):
            cleaned = form.cleaned_data

            is_active = bool(cleaned.get("is_active", True))
            is_streamable = bool(cleaned.get("is_streamable", True))
            is_default = bool(cleaned.get("is_default", False))

            if is_default and (not is_active or not is_streamable):
                cleaned["is_default"] = False
                form.instance.is_default = False
                is_default = False

            if is_active and is_streamable:
                playable_forms.append(form)

            if is_active and is_streamable and is_default:
                selected_forms.append(form)

        if len(selected_forms) > 1:
            raise ValidationError(
                "Only one active streamable variant can be "
                "the track default."
            )

        if not selected_forms and playable_forms:
            chosen = playable_forms[0]
            chosen.cleaned_data["is_default"] = True
            chosen.instance.is_default = True


# -------------------------------------------------
# Canonical contributors
# -------------------------------------------------


class AudioContributorAdminForm(forms.ModelForm):
    """
    Canonical contributor editor.

    Prevents accidental duplicates without changing the database model.
    """

    class Meta:
        model = AudioContributor
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        display_name = " ".join(
            str(cleaned.get("display_name") or "").split()
        )
        legal_name = " ".join(
            str(cleaned.get("legal_name") or "").split()
        )
        external_reference = str(
            cleaned.get("external_reference") or ""
        ).strip()
        kind = cleaned.get("kind")

        cleaned["display_name"] = display_name
        cleaned["legal_name"] = legal_name
        cleaned["external_reference"] = external_reference

        if not display_name or not kind:
            return cleaned

        existing = AudioContributor.objects.all()

        if self.instance and self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if external_reference:
            duplicate_reference = existing.filter(
                external_reference__iexact=external_reference
            ).exists()

            if duplicate_reference:
                self.add_error(
                    "external_reference",
                    (
                        "Another Audio Contributor already uses this "
                        "external reference."
                    ),
                )

        same_identity = existing.filter(
            display_name__iexact=display_name,
            kind=kind,
        )

        if legal_name:
            same_identity = same_identity.filter(
                legal_name__iexact=legal_name
            )

            if same_identity.exists():
                self.add_error(
                    "display_name",
                    (
                        "This Audio Contributor already exists. "
                        "Use the existing canonical contributor instead "
                        "of creating a duplicate."
                    ),
                )

        elif same_identity.exists():
            self.add_error(
                "display_name",
                (
                    "A contributor with this display name and kind "
                    "already exists. Use the existing contributor, or "
                    "provide a legal name if this is a different entity."
                ),
            )

        return cleaned


class TrackContributorInlineForm(forms.ModelForm):
    """
    Connect a MusicTrack to one canonical AudioContributor.

    The contributor itself is never duplicated inside TrackContributor.
    """

    class Meta:
        model = TrackContributor
        fields = (
            "contributor",
            "role",
            "credit_text",
            "share_basis_points",
            "sort_order",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        current_contributor_id = getattr(
            self.instance,
            "contributor_id",
            None,
        )

        queryset = AudioContributor.objects.filter(is_active=True)

        # Preserve an existing historical relationship even if that
        # contributor was later marked inactive.
        if current_contributor_id:
            queryset = AudioContributor.objects.filter(
                Q(is_active=True) | Q(pk=current_contributor_id)
            )

        self.fields["contributor"].queryset = queryset.order_by(
            "display_name",
            "legal_name",
            "id",
        )

        self.fields["contributor"].empty_label = (
            "Select an existing Audio Contributor"
        )
        self.fields["contributor"].help_text = (
            "Select the canonical contributor defined in Audio "
            "Contributors. If the person or organization does not "
            "exist yet, use the + button beside this field to create "
            "it once, then reuse it for every track."
        )
        self.fields["role"].help_text = (
            "The contributor's role on this specific track."
        )
        self.fields["credit_text"].help_text = (
            "Optional public-facing credit, e.g. Performed by Paul Pitman."
        )
        self.fields["share_basis_points"].help_text = (
            "Normally leave at 0. Use only for a documented contractual "
            "or rights share."
        )

    def clean(self):
        cleaned = super().clean()
        contributor = cleaned.get("contributor")

        if contributor and not contributor.is_active:
            current_id = getattr(self.instance, "contributor_id", None)

            if contributor.pk != current_id:
                self.add_error(
                    "contributor",
                    (
                        "This contributor is inactive. Reactivate it in "
                        "Audio Contributors before assigning it to a new track."
                    ),
                )

        return cleaned


class TrackContributorInlineFormSet(BaseInlineFormSet):
    """
    Prevent duplicate contributor-role pairs inside one track.
    """

    def clean(self):
        super().clean()

        if any(self.errors):
            return

        seen = set()

        for form in _meaningful_inline_forms(self):
            contributor = form.cleaned_data.get("contributor")
            role = form.cleaned_data.get("role")

            if contributor is None or not role:
                continue

            key = (contributor.pk, role)

            if key in seen:
                raise ValidationError(
                    (
                        f"{contributor} is already assigned to this "
                        f"track with the role "
                        f"{dict(TrackContributor.Role.choices).get(role, role)}."
                    )
                )

            seen.add(key)