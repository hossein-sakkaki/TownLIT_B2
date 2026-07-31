# apps/creative_editor/tests/test_asset_permission.py

from __future__ import annotations

from django.contrib.auth.models import (
    AnonymousUser,
)
from django.test import TestCase

from apps.creative_editor.services.compositions import (
    create_composition,
)
from apps.creative_editor.tests.factories import (
    build_test_document,
    composition_data,
    create_test_user,
    ensure_test_font,
)


class CreativeAssetPermissionTests(
    TestCase
):
    """
    Test composition asset authorization.
    """

    def setUp(self):
        ensure_test_font()

        self.owner = create_test_user(
            email=(
                "creative-owner@example.com"
            ),
        )

        self.other_user = create_test_user(
            email=(
                "creative-other@example.com"
            ),
        )

        document = build_test_document()

        self.composition = (
            create_composition(
                owner=self.owner,
                validated_data=(
                    composition_data(
                        document
                    )
                ),
            )
        )

    def test_owner_can_access_rendered_asset(
        self,
    ):
        allowed = (
            self.composition
            .can_deliver_asset(
                viewer=self.owner,
                field_name=(
                    "rendered_image"
                ),
                intent="view",
            )
        )

        self.assertTrue(
            allowed
        )

    def test_other_user_cannot_access_private_asset(
        self,
    ):
        allowed = (
            self.composition
            .can_deliver_asset(
                viewer=self.other_user,
                field_name=(
                    "rendered_image"
                ),
                intent="view",
            )
        )

        self.assertFalse(
            allowed
        )

    def test_anonymous_user_cannot_access_private_asset(
        self,
    ):
        allowed = (
            self.composition
            .can_deliver_asset(
                viewer=AnonymousUser(),
                field_name=(
                    "rendered_image"
                ),
                intent="view",
            )
        )

        self.assertFalse(
            allowed
        )

    def test_unknown_field_is_rejected(
        self,
    ):
        allowed = (
            self.composition
            .can_deliver_asset(
                viewer=self.owner,
                field_name=(
                    "unknown_file"
                ),
                intent="view",
            )
        )

        self.assertFalse(
            allowed
        )