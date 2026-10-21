# apps/organization_content/tests/test_update_validation.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.organization_content.models import OrganizationUpdate


class OrganizationUpdateValidationTests(SimpleTestCase):
    def make_update(self, **values):
        return OrganizationUpdate(
            organization_id=17,
            created_by_id=23,
            **{"caption": "Welcome to our Organization", **values},
        )

    def validate(self, update):
        # Foreign key existence and uniqueness are separate database checks.
        update.full_clean(
            exclude=["organization", "created_by"],
            validate_unique=False,
            validate_constraints=False,
        )

    def test_new_draft_does_not_require_a_publisher(self):
        update = self.make_update()

        self.validate(update)

        self.assertEqual(update.status, OrganizationUpdate.Status.DRAFT)
        self.assertIsNone(update.published_by_id)
        self.assertIsNone(update.published_at)

    def test_published_update_still_requires_a_timestamp(self):
        update = self.make_update(status=OrganizationUpdate.Status.PUBLISHED)

        with self.assertRaises(ValidationError) as raised:
            self.validate(update)

        self.assertIn("published_at", raised.exception.message_dict)
        self.assertNotIn("published_by", raised.exception.message_dict)

    def test_blank_caption_is_still_rejected(self):
        update = self.make_update(caption="   ")

        with self.assertRaises(ValidationError) as raised:
            self.validate(update)

        self.assertIn("caption", raised.exception.message_dict)
