# utils/email/core/renderer.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from dataclasses import dataclass
import logging

from django.template.loader import (
    TemplateDoesNotExist,
    render_to_string,
)
from django.utils.html import strip_tags


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RenderedEmail:
    html: str
    text: str


def render_email_template(
    *,
    template_path: str,
    context: dict | None = None,
    text_template_path: str | None = None,
) -> RenderedEmail:
    """
    Render HTML and plain-text email content.
    """

    render_context = context or {}

    html_content = _render_html(
        template_path=template_path,
        context=render_context,
    )

    text_content = _render_text(
        html_content=html_content,
        text_template_path=text_template_path,
        context=render_context,
    )

    return RenderedEmail(
        html=html_content,
        text=text_content,
    )


def _render_html(
    *,
    template_path: str,
    context: dict,
) -> str:
    """
    Render the HTML email template.
    """

    try:
        return render_to_string(
            template_path,
            context,
        )
    except TemplateDoesNotExist:
        logger.warning(
            "Email template not found: %s. "
            "Using minimal fallback HTML.",
            template_path,
        )

        fallback_text = strip_tags(
            str(context)
        )

        return (
            "<html>"
            "<body>"
            f"<pre>{fallback_text}</pre>"
            "</body>"
            "</html>"
        )


def _render_text(
    *,
    html_content: str,
    text_template_path: str | None,
    context: dict,
) -> str:
    """
    Render or derive the plain-text email body.
    """

    if not text_template_path:
        return strip_tags(html_content)

    try:
        return render_to_string(
            text_template_path,
            context,
        )
    except TemplateDoesNotExist:
        logger.warning(
            "Text email template not found: %s. "
            "Using HTML fallback text.",
            text_template_path,
        )

        return strip_tags(html_content)