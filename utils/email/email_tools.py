# utils/email/email_tools.py
from django.template.loader import render_to_string, TemplateDoesNotExist
from django.utils.html import strip_tags
from utils.common.utils import send_email
import logging

logger = logging.getLogger(__name__)

def send_custom_email(to, subject, template_path, context=None, text_template_path=None):
    context = context or {}

    try:
        # Try HTML template
        try:
            html_content = render_to_string(template_path, context)
        except TemplateDoesNotExist:
            logger.warning("Email template not found: %s (fallback to minimal HTML)", template_path)
            # minimal fallback
            html_content = f"<html><body><pre>{strip_tags(str(context))}</pre></body></html>"

        # Plain text fallback
        if text_template_path:
            try:
                text_content = render_to_string(text_template_path, context)
            except TemplateDoesNotExist:
                logger.warning("Text template not found: %s (fallback to strip_tags)", text_template_path)
                text_content = strip_tags(html_content)
        else:
            text_content = strip_tags(html_content)

        success = send_email(subject, text_content, html_content, to)
        if not success:
            logger.warning("❌ Email not sent to %s. Check SES/SMTP logs.", to)
        return success

    except Exception as e:
        logger.exception("❌ Failed to send email to %s: %s", to, e)
        return False
