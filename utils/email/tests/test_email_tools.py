# utils/email/tests/test_email_tools.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from unittest.mock import patch

from django.test import SimpleTestCase

from utils.email.email_tools import (
    send_custom_email,
)


class SendCustomEmailTests(SimpleTestCase):
    @patch(
        "utils.email.email_tools."
        "send_ses_email"
    )
    def test_standard_email_uses_standard_sender(
        self,
        send_mock,
    ):
        send_mock.return_value = True

        success = send_custom_email(
            to="test@townlit.com",
            subject="Test",
            template_path=(
                "emails/tests/"
                "missing_template.html"
            ),
            context={
                "first_name": "Gabby",
            },
        )

        self.assertTrue(success)
        send_mock.assert_called_once()

    @patch(
        "utils.email.email_tools."
        "send_ses_email_with_attachments"
    )
    def test_attachment_email_uses_raw_sender(
        self,
        send_mock,
    ):
        send_mock.return_value = True

        success = send_custom_email(
            to="test@townlit.com",
            subject="Test",
            template_path=(
                "emails/tests/"
                "missing_template.html"
            ),
            context={
                "first_name": "Gabby",
            },
            attachments=[
                {
                    "filename": "test.pdf",
                    "content": b"pdf",
                    "mime_type": "application/pdf",
                }
            ],
        )

        self.assertTrue(success)
        send_mock.assert_called_once()