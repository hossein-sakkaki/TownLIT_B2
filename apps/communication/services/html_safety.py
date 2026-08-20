# apps/communication/services/html_safety.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


import nh3

from django.core.exceptions import ValidationError


RICH_TEXT_MAX_LENGTH = 50_000
CUSTOM_HTML_MAX_LENGTH = 100_000


RICH_TEXT_TAGS = {
    "p",
    "div",
    "span",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "a",
    "ul",
    "ol",
    "li",
    "blockquote",
}


CUSTOM_HTML_TAGS = RICH_TEXT_TAGS | {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "table",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "td",
    "th",
    "img",
}


RICH_TEXT_ATTRIBUTES = {
    "*": {
        "style",
        "dir",
        "title",
    },
    "a": {
        "href",
        "target",
    },
}


CUSTOM_HTML_ATTRIBUTES = {
    "*": {
        "style",
        "dir",
        "title",
        "role",
    },
    "a": {
        "href",
        "target",
    },
    "img": {
        "src",
        "alt",
        "width",
        "height",
    },
    "table": {
        "width",
        "cellpadding",
        "cellspacing",
        "border",
        "align",
        "bgcolor",
    },
    "td": {
        "width",
        "height",
        "colspan",
        "rowspan",
        "align",
        "valign",
        "bgcolor",
    },
    "th": {
        "width",
        "height",
        "colspan",
        "rowspan",
        "align",
        "valign",
        "bgcolor",
    },
}


RICH_TEXT_STYLE_PROPERTIES = {
    "color",
    "background-color",
    "font-size",
    "font-style",
    "font-weight",
    "text-decoration",
    "text-align",
    "direction",
    "unicode-bidi",
    "line-height",
    "letter-spacing",
    "white-space",
}


CUSTOM_HTML_STYLE_PROPERTIES = (
    RICH_TEXT_STYLE_PROPERTIES
    | {
        "font-family",
        "width",
        "height",
        "max-width",
        "min-width",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "border",
        "border-width",
        "border-style",
        "border-color",
        "border-radius",
        "border-collapse",
        "display",
        "vertical-align",
    }
)


URL_SCHEMES = {
    "http",
    "https",
    "mailto",
    "tel",
}


CLEAN_CONTENT_TAGS = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "form",
    "svg",
    "math",
}


def _attribute_filter(
    tag,
    attribute,
    value,
):
    if attribute == "dir":
        normalized = value.strip().lower()

        if normalized not in {
            "ltr",
            "rtl",
            "auto",
        }:
            return None

        return normalized

    if attribute == (
        "data-townlit-rich-direction"
    ):
        normalized = value.strip().lower()

        if normalized not in {
            "ltr",
            "rtl",
        }:
            return None

        return normalized

    if attribute == "target":
        if value not in {
            "_blank",
            "_self",
        }:
            return None

    return value


_RICH_TEXT_CLEANER = nh3.Cleaner(
    tags=RICH_TEXT_TAGS,
    clean_content_tags=CLEAN_CONTENT_TAGS,
    attributes=RICH_TEXT_ATTRIBUTES,
    attribute_filter=_attribute_filter,
    strip_comments=True,
    link_rel="noopener noreferrer",
    generic_attribute_prefixes={
        "data-townlit-",
    },
    url_schemes=URL_SCHEMES,
    filter_style_properties=(
        RICH_TEXT_STYLE_PROPERTIES
    ),
    url_relative="deny",
)


_CUSTOM_HTML_CLEANER = nh3.Cleaner(
    tags=CUSTOM_HTML_TAGS,
    clean_content_tags=CLEAN_CONTENT_TAGS,
    attributes=CUSTOM_HTML_ATTRIBUTES,
    attribute_filter=_attribute_filter,
    strip_comments=True,
    link_rel="noopener noreferrer",
    generic_attribute_prefixes={
        "data-townlit-",
        "aria-",
    },
    url_schemes=URL_SCHEMES,
    filter_style_properties=(
        CUSTOM_HTML_STYLE_PROPERTIES
    ),
    url_relative="deny",
)


class EmailHTMLSafetyService:
    """
    Sanitize admin-authored email HTML before persistence.
    """

    @classmethod
    def sanitize_rich_text(
        cls,
        value,
    ):
        return cls._clean(
            value=value,
            cleaner=_RICH_TEXT_CLEANER,
            max_length=RICH_TEXT_MAX_LENGTH,
            label="Rich text",
        )

    @classmethod
    def sanitize_custom_html(
        cls,
        value,
    ):
        return cls._clean(
            value=value,
            cleaner=_CUSTOM_HTML_CLEANER,
            max_length=CUSTOM_HTML_MAX_LENGTH,
            label="Custom HTML",
        )

    @staticmethod
    def _clean(
        *,
        value,
        cleaner,
        max_length,
        label,
    ):
        value = (
            str(value)
            if value is not None
            else ""
        ).strip()

        if not value:
            return ""

        if len(value) > max_length:
            raise ValidationError(
                (
                    f"{label} is too large. "
                    f"Maximum length is "
                    f"{max_length:,} characters."
                )
            )

        cleaned = cleaner.clean(
            value
        ).strip()

        return cleaned