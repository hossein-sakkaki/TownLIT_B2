# apps/communication/forms/blocks.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.

from django import forms
from ckeditor_uploader.widgets import CKEditorUploadingWidget
from django.core.validators import URLValidator

from apps.communication.constants import EmailBlockType
from apps.communication.models import (
    EmailCampaignBlock,
    EmailTemplateBlock,
)
from apps.communication.services.html_safety import (
    EmailHTMLSafetyService,
)


ALIGN_CHOICES = [
    ("left", "Left"),
    ("center", "Center"),
    ("right", "Right"),
]

IMAGE_WIDTH_CHOICES = (
    (120, "Extra Small"),
    (160, "Small"),
    (240, "Compact"),
    (320, "Medium"),
    (520, "Large"),
    (700, "Full Width"),
)


class BaseEmailBlockAdminForm(forms.ModelForm):
    headline = forms.CharField(
        required=False,
        label="Headline / Title",
        help_text="Used by Hero and Callout blocks.",
    )

    content = forms.CharField(
        required=False,
        label="Main Content",
        widget=CKEditorUploadingWidget(),
    )

    secondary_content = forms.CharField(
        required=False,
        label="Second Column Content",
        widget=CKEditorUploadingWidget(),
        help_text="Used only by Two Columns blocks.",
    )

    image_url = forms.URLField(
        required=False,
        label="Image URL",
    )

    image_alt = forms.CharField(
        required=False,
        label="Image Alt Text",
    )

    image_width = forms.TypedChoiceField(
        required=False,
        coerce=int,
        choices=IMAGE_WIDTH_CHOICES,
        initial=320,
        label="Image Size",
    )

    image_link_url = forms.URLField(
        required=False,
        label="Image Destination URL",
        help_text=(
            "Optional. When provided, clicking the image "
            "opens this destination."
        ),
    )

    action_label = forms.CharField(
        required=False,
        max_length=120,
        label="Button Label",
    )

    action_url = forms.URLField(
        required=False,
        label="Button Destination URL",
    )

    attribution = forms.CharField(
        required=False,
        max_length=160,
        label="Quote Attribution",
    )

    alignment = forms.ChoiceField(
        required=False,
        choices=ALIGN_CHOICES,
        initial="left",
        label="Alignment",
    )

    spacer_height = forms.IntegerField(
        required=False,
        min_value=4,
        max_value=120,
        initial=24,
        label="Spacer Height",
    )

    social_links = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 4}
        ),
        label="Social Links",
        help_text=(
            "One per line: "
            "Label | https://example.com"
        ),
    )

    custom_html = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"rows": 8}
        ),
        label="Custom HTML",
        help_text="Advanced use only.",
    )

    class Meta:
        fields = [
            "block_type",
            "name",
            "sort_order",
            "is_enabled",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance or not self.instance.pk:
            return

        data = self.instance.data or {}
        block_type = self.instance.block_type

        if block_type == EmailBlockType.HERO:
            self.fields["headline"].initial = (
                data.get("title", "")
            )
            self.fields["content"].initial = (
                data.get("html", "")
            )
            self.fields["image_url"].initial = (
                data.get("image_url", "")
            )
            self.fields["image_alt"].initial = (
                data.get("image_alt", "")
            )
            self.fields["image_width"].initial = (
                data.get("image_width", 320)
            )
            self.fields["image_link_url"].initial = (
                data.get("image_link_url", "")
            )
            self.fields["action_label"].initial = (
                data.get("button_label", "")
            )
            self.fields["action_url"].initial = (
                data.get("button_url", "")
            )
            self.fields["alignment"].initial = (
                data.get("align", "center")
            )

        elif block_type == EmailBlockType.TEXT:
            self.fields["content"].initial = (
                data.get("html", "")
            )
            self.fields["alignment"].initial = (
                data.get("align", "left")
            )

        elif block_type == EmailBlockType.IMAGE:
            self.fields["image_url"].initial = (
                data.get("url", "")
            )
            self.fields["image_alt"].initial = (
                data.get("alt", "")
            )
            self.fields["image_width"].initial = (
                data.get("width", 320)
            )
            self.fields["image_link_url"].initial = (
                data.get("link_url", "")
            )
            self.fields["alignment"].initial = (
                data.get("align", "center")
            )

        elif block_type == EmailBlockType.BUTTON:
            self.fields["action_label"].initial = (
                data.get("label", "")
            )
            self.fields["action_url"].initial = (
                data.get("url", "")
            )
            self.fields["alignment"].initial = (
                data.get("align", "center")
            )

        elif block_type == EmailBlockType.QUOTE:
            self.fields["content"].initial = (
                data.get("quote", "")
            )
            self.fields["attribution"].initial = (
                data.get("attribution", "")
            )

        elif block_type == EmailBlockType.CALLOUT:
            self.fields["headline"].initial = (
                data.get("title", "")
            )
            self.fields["content"].initial = (
                data.get("html", "")
            )

        elif block_type == EmailBlockType.SPACER:
            self.fields["spacer_height"].initial = (
                data.get("height", 24)
            )

        elif block_type == EmailBlockType.TWO_COLUMN:
            self.fields["content"].initial = (
                data.get("left_html", "")
            )
            self.fields["secondary_content"].initial = (
                data.get("right_html", "")
            )

        elif block_type == EmailBlockType.SOCIAL_LINKS:
            links = data.get("links", [])

            self.fields["social_links"].initial = "\n".join(
                (
                    f"{item.get('label', '')} | "
                    f"{item.get('url', '')}"
                )
                for item in links
            )

        elif block_type == EmailBlockType.CUSTOM_HTML:
            self.fields["custom_html"].initial = (
                data.get("html", "")
            )

    def clean(self):
        cleaned = super().clean()

        if not cleaned:
            return cleaned

        block_type = cleaned.get("block_type")

        if (
            block_type == EmailBlockType.TEXT
            and not cleaned.get("content")
        ):
            self.add_error(
                "content",
                "Text blocks need content.",
            )

        if (
            block_type == EmailBlockType.IMAGE
            and not cleaned.get("image_url")
        ):
            self.add_error(
                "image_url",
                "Image blocks need an image URL.",
            )

        if block_type == EmailBlockType.BUTTON:
            if not cleaned.get("action_label"):
                self.add_error(
                    "action_label",
                    "Button label is required.",
                )

            if not cleaned.get("action_url"):
                self.add_error(
                    "action_url",
                    "Button URL is required.",
                )

        if block_type == EmailBlockType.TWO_COLUMN:
            if (
                not cleaned.get("content")
                and not cleaned.get(
                    "secondary_content"
                )
            ):
                raise forms.ValidationError(
                    "Two Columns blocks need content "
                    "in at least one column."
                )

        if (
            block_type == EmailBlockType.CUSTOM_HTML
            and not cleaned.get("custom_html")
        ):
            self.add_error(
                "custom_html",
                "Custom HTML cannot be empty.",
            )

        return cleaned

    def clean_social_links(self):
        value = (
            self.cleaned_data.get(
                "social_links"
            )
            or ""
        ).strip()

        if not value:
            return ""

        validator = URLValidator(
            schemes=[
                "http",
                "https",
            ]
        )

        for line in value.splitlines():
            line = line.strip()

            if not line:
                continue

            if "|" not in line:
                raise forms.ValidationError(
                    "Each social link must contain "
                    "a label and URL."
                )

            label, url = line.split(
                "|",
                1,
            )

            label = label.strip()
            url = url.strip()

            if not label:
                raise forms.ValidationError(
                    "Each social link needs a label."
                )

            try:
                validator(url)
            except forms.ValidationError as exc:
                raise forms.ValidationError(
                    f"Invalid social link URL: {url}"
                ) from exc

        return value

    def clean_headline(self):
        return (
            EmailHTMLSafetyService
            .sanitize_rich_text(
                self.cleaned_data.get(
                    "headline"
                )
            )
        )

    def clean_content(self):
        return (
            EmailHTMLSafetyService
            .sanitize_rich_text(
                self.cleaned_data.get(
                    "content"
                )
            )
        )

    def clean_secondary_content(self):
        return (
            EmailHTMLSafetyService
            .sanitize_rich_text(
                self.cleaned_data.get(
                    "secondary_content"
                )
            )
        )

    def clean_custom_html(self):
        return (
            EmailHTMLSafetyService
            .sanitize_custom_html(
                self.cleaned_data.get(
                    "custom_html"
                )
            )
        )

    def save(self, commit=True):
        instance = super().save(
            commit=False
        )

        instance.data = (
            self._build_data()
        )

        if commit:
            instance.save()

        return instance

    def _build_data(self):
        cleaned = self.cleaned_data
        block_type = cleaned.get(
            "block_type"
        )

        if block_type == EmailBlockType.HERO:
            return {
                "title": (
                    cleaned.get(
                        "headline"
                    )
                    or ""
                ),
                "html": (
                    cleaned.get(
                        "content"
                    )
                    or ""
                ),
                "image_url": (
                    cleaned.get(
                        "image_url"
                    )
                    or ""
                ),
                "image_alt": (
                    cleaned.get(
                        "image_alt"
                    )
                    or ""
                ),
                "image_width": (
                    cleaned.get(
                        "image_width"
                    )
                    or 320
                ),
                "image_link_url": (
                    cleaned.get(
                        "image_link_url"
                    )
                    or ""
                ),
                "button_label": (
                    cleaned.get(
                        "action_label"
                    )
                    or ""
                ),
                "button_url": (
                    cleaned.get(
                        "action_url"
                    )
                    or ""
                ),
                "align": (
                    cleaned.get(
                        "alignment"
                    )
                    or "center"
                ),
            }

        if block_type == EmailBlockType.TEXT:
            return {
                "html": (
                    cleaned.get(
                        "content"
                    )
                    or ""
                ),
                "align": (
                    cleaned.get(
                        "alignment"
                    )
                    or "left"
                ),
            }

        if block_type == EmailBlockType.IMAGE:
            return {
                "url": (
                    cleaned.get(
                        "image_url"
                    )
                    or ""
                ),
                "alt": (
                    cleaned.get(
                        "image_alt"
                    )
                    or ""
                ),
                "link_url": (
                    cleaned.get(
                        "image_link_url"
                    )
                    or ""
                ),
                "width": (
                    cleaned.get(
                        "image_width"
                    )
                    or 320
                ),
                "align": (
                    cleaned.get(
                        "alignment"
                    )
                    or "center"
                ),
            }

        if block_type == EmailBlockType.BUTTON:
            return {
                "label": (
                    cleaned.get(
                        "action_label"
                    )
                    or ""
                ),
                "url": (
                    cleaned.get(
                        "action_url"
                    )
                    or ""
                ),
                "align": (
                    cleaned.get(
                        "alignment"
                    )
                    or "center"
                ),
            }

        if block_type == EmailBlockType.QUOTE:
            return {
                "quote": (
                    cleaned.get(
                        "content"
                    )
                    or ""
                ),
                "attribution": (
                    cleaned.get(
                        "attribution"
                    )
                    or ""
                ),
            }

        if block_type == EmailBlockType.CALLOUT:
            return {
                "title": (
                    cleaned.get(
                        "headline"
                    )
                    or ""
                ),
                "html": (
                    cleaned.get(
                        "content"
                    )
                    or ""
                ),
            }

        if block_type == EmailBlockType.DIVIDER:
            return {}

        if block_type == EmailBlockType.SPACER:
            return {
                "height": (
                    cleaned.get(
                        "spacer_height"
                    )
                    or 24
                ),
            }

        if block_type == EmailBlockType.TWO_COLUMN:
            return {
                "left_html": (
                    cleaned.get(
                        "content"
                    )
                    or ""
                ),
                "right_html": (
                    cleaned.get(
                        "secondary_content"
                    )
                    or ""
                ),
            }

        if block_type == EmailBlockType.SOCIAL_LINKS:
            return {
                "links": (
                    self._parse_social_links(
                        cleaned.get(
                            "social_links",
                            "",
                        )
                    )
                ),
            }

        if block_type == EmailBlockType.CUSTOM_HTML:
            return {
                "html": (
                    cleaned.get(
                        "custom_html"
                    )
                    or ""
                ),
            }

        return {}

    def _parse_social_links(
        self,
        value,
    ):
        links = []

        for line in (
            value or ""
        ).splitlines():
            line = line.strip()

            if not line:
                continue

            label, url = line.split(
                "|",
                1,
            )

            links.append(
                {
                    "label": (
                        label.strip()
                    ),
                    "url": (
                        url.strip()
                    ),
                }
            )

        return links


class EmailCampaignBlockAdminForm(
    BaseEmailBlockAdminForm
):
    class Meta(
        BaseEmailBlockAdminForm.Meta
    ):
        model = EmailCampaignBlock


class EmailTemplateBlockAdminForm(
    BaseEmailBlockAdminForm
):
    class Meta(
        BaseEmailBlockAdminForm.Meta
    ):
        model = EmailTemplateBlock