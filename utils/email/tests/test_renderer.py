# utils/email/tests/test_renderer.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from django.test import SimpleTestCase

from utils.email.core.renderer import (
    render_email_template,
)


class EmailRendererTests(SimpleTestCase):
    def test_missing_template_uses_fallback_html(self):
        rendered = render_email_template(
            template_path=(
                "emails/tests/"
                "missing_template.html"
            ),
            context={
                "first_name": "Gabby",
            },
        )

        self.assertIn(
            "Gabby",
            rendered.html,
        )
        self.assertIn(
            "Gabby",
            rendered.text,
        )