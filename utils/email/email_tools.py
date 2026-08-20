# utils/email/email_tools.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


import logging

from utils.email.core.renderer import (
    render_email_template,
)

from utils.email.core.ses_sender import (
    send_email,
    send_email_with_attachments,
)


logger = logging.getLogger(__name__)


def send_custom_email(
    to,
    subject,
    template_path,
    context=None,
    text_template_path=None,
    attachments=None,
):
    """
    Render and send TownLIT email.
    """

    try:

        rendered = render_email_template(
            template_path=template_path,
            context=context,
            text_template_path=text_template_path,
        )

        if attachments:

            return send_email_with_attachments(
                subject,
                rendered.text,
                rendered.html,
                to,
                attachments,
            )

        return send_email(
            subject,
            rendered.text,
            rendered.html,
            to,
        )

    except Exception as error:

        logger.exception(
            "Email failed: %s",
            error,
        )

        return False