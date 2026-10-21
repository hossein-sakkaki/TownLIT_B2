# apps/posts/tests/test_organization_comment_identity.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-20.
# Last Update by Hossein Sakkaki on 2026-10-20.

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.posts.serializers.comments import (
    SimpleCommentReadSerializer, RootCommentReadSerializer, CommentReadSerializer,
)
from apps.posts.services.organization_comment_identity import (
    legacy_public_name, public_organization_identity,
    validate_comment_organization,
)


class PublicOrganizationCommentIdentityTests(SimpleTestCase):
    def setUp(self):
        self.organization = SimpleNamespace(
            pk=24, id=24, name="Community Organization", slug="community-org",
            logo=SimpleNamespace(url="/media/logo.png"),
        )
        self.comment = SimpleNamespace(
            pk=101, id=101, name=SimpleNamespace(
                id=935, username="private-person", name="Private", family="Operator",
            ),
            acting_organization_id=24,
            acting_organization=self.organization,
        )

    def test_legacy_read_name_never_contains_operator_identity(self):
        for serializer_class in (
            SimpleCommentReadSerializer, RootCommentReadSerializer, CommentReadSerializer,
        ):
            serializer = serializer_class(context={})
            display = serializer.get_name(self.comment)
            self.assertEqual(display["id"], -24)
            self.assertEqual(display["name"], "Community Organization")
            self.assertNotIn("private-person", str(display))
            self.assertNotIn("935", str(display))
            self.assertEqual(
                serializer.get_organization_identity(self.comment)["id"], 24,
            )

    def test_organization_comment_requires_own_target(self):
        actor = SimpleNamespace(pk=935, is_authenticated=True)
        content_type = SimpleNamespace(app_label="organization_content", model="organizationupdate")
        update = SimpleNamespace(organization_id=100, organization=self.organization)
        with patch(
            "apps.organization_content.models.OrganizationUpdate.objects"
        ) as manager, patch(
            "apps.posts.services.organization_comment_identity.ensure_update_interaction_access"
        ):
            manager.select_related.return_value.get.return_value = update
            with self.assertRaises(PermissionDenied):
                validate_comment_organization(
                    user=actor, organization_id=24,
                    content_type=content_type, object_id=1000,
                )

    def test_organization_comment_requires_strict_permission(self):
        actor = SimpleNamespace(pk=935, is_authenticated=True)
        self.organization.status = "active"
        update = SimpleNamespace(organization_id=24, organization=self.organization)
        content_type = SimpleNamespace(app_label="organization_content", model="organizationupdate")
        with patch(
            "apps.organization_content.models.OrganizationUpdate.objects"
        ) as manager, patch(
            "apps.posts.services.organization_comment_identity.ensure_update_interaction_access"
        ), patch(
            "apps.posts.services.organization_comment_identity.user_has_organization_permission_strict",
            return_value=False,
        ):
            manager.select_related.return_value.get.return_value = update
            with self.assertRaises(PermissionDenied):
                validate_comment_organization(
                    user=actor, organization_id=24,
                    content_type=content_type, object_id=1000,
                )
