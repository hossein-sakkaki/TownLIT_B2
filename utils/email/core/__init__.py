# utils/email/core/__init__.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from .renderer import (
    RenderedEmail,
    render_email_template,
)

from .ses_sender import (
    send_email,
    send_email_with_attachments,
)


__all__ = [
    "RenderedEmail",
    "render_email_template",
    "send_email",
    "send_email_with_attachments",
]