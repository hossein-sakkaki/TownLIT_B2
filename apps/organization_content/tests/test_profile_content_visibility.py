# apps/organization_content/tests/test_profile_content_visibility.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock, patch

from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organization_content.models import OrganizationFeedEntry, OrganizationUpdate
from apps.organization_content.services import access as content_access, feed as feed_service
from apps.organization_content.views import feed as feed_views
from apps.organization_media.services import access as media_access
from apps.organizations.models import Organization
from apps.sanctuary.services import held_content_access


class OrganizationProfileContentTests(SimpleTestCase):
    def setUp(self):
        self.viewer = SimpleNamespace(pk=42, is_authenticated=True, is_staff=False)
        self.anonymous = SimpleNamespace(is_authenticated=False)
        self.organization = Organization(
            pk=17, slug="test-unlisted", status="active", visibility="unlisted",
        )
        self.update = OrganizationUpdate(
            pk=23, organization=self.organization, caption="Welcome",
            status="published", published_at=timezone.now() - timedelta(minutes=1),
            caption_safety_verified=True,
        )
        self.asset = SimpleNamespace(is_ready_for_publication=MagicMock(return_value=True))
        self.media_items = MagicMock()
        self.media_items.all.return_value = [SimpleNamespace(asset=self.asset)]
        self.descriptor = patch.object(OrganizationUpdate, "media_items", new_callable=PropertyMock)
        self.descriptor.start().return_value = self.media_items
        self.addCleanup(self.descriptor.stop)
        self.hold = patch.object(held_content_access, "is_under_active_safety_hold", return_value=False)
        self.is_held = self.hold.start()
        self.addCleanup(self.hold.stop)

    def test_profile_access_matrix(self):
        for visibility in ("public", "unlisted", "private", "unknown"):
            for status in ("active", "suspended", "closed"):
                for viewer in (self.viewer, self.anonymous, None):
                    with self.subTest(visibility=visibility, status=status, viewer=viewer):
                        self.organization.visibility = visibility
                        self.organization.status = status
                        expected = status == "active" and (
                            visibility == "public" or visibility == "unlisted" and viewer is self.viewer
                        )
                        self.assertEqual(content_access.can_view_organization_content(
                            organization=self.organization, viewer=viewer,
                        ), expected)

    def test_published_ready_unlisted_post_is_visible_to_signed_in_visitor(self):
        self.assertTrue(self.update.content_visibility_allowed(viewer=self.viewer))
        self.assertTrue(self.update.is_available())
        self.asset.is_ready_for_publication.assert_called()

    def test_anonymous_unlisted_post_is_hidden_while_public_post_remains_visible(self):
        self.assertFalse(self.update.content_visibility_allowed(viewer=self.anonymous))
        self.organization.visibility = "public"
        self.assertTrue(self.update.content_visibility_allowed(viewer=self.anonymous))

    def test_private_and_inactive_organization_posts_stay_hidden(self):
        for visibility, status in (("private", "active"), ("unlisted", "suspended"), ("public", "closed")):
            with self.subTest(visibility=visibility, status=status):
                self.organization.visibility, self.organization.status = visibility, status
                self.assertFalse(self.update.content_visibility_allowed(viewer=self.viewer))

    def test_publication_and_moderation_gates_remain_required(self):
        cases = (
            ("status", "draft"), ("status", "archived"),
            ("published_at", None), ("published_at", timezone.now() + timedelta(hours=1)),
            ("caption_safety_verified", False), ("is_active", False), ("is_suspended", True),
        )
        for field, value in cases:
            original = getattr(self.update, field)
            with self.subTest(field=field, value=value):
                setattr(self.update, field, value)
                self.assertFalse(self.update.content_visibility_allowed(viewer=self.viewer))
            setattr(self.update, field, original)

    def test_safety_hold_and_unready_media_still_hide_the_post(self):
        self.is_held.return_value = True
        self.assertFalse(self.update.content_visibility_allowed(viewer=self.viewer))
        self.is_held.return_value = False
        self.asset.is_ready_for_publication.return_value = False
        self.assertFalse(self.update.content_visibility_allowed(viewer=self.viewer))

    def test_unlisted_feed_returns_only_available_posts_from_the_same_organization(self):
        draft = OrganizationUpdate(pk=24, organization=self.organization, caption="Draft", status="draft")
        foreign = OrganizationUpdate(
            pk=25, organization=Organization(pk=18, status="active", visibility="public"),
            caption="Other Organization", status="published", caption_safety_verified=True,
            published_at=timezone.now() - timedelta(minutes=1),
        )
        entry = SimpleNamespace(content_object=self.update)
        with patch.object(OrganizationFeedEntry, "objects") as manager:
            queryset = manager.filter.return_value
            queryset.filter.return_value.select_related.return_value.order_by.return_value = [
                entry, SimpleNamespace(content_object=draft), SimpleNamespace(content_object=foreign),
            ]
            now = timezone.now()
            result = feed_service.visible_feed(self.organization, viewer=self.viewer, now=now)
        self.assertEqual(result, [entry])
        manager.filter.assert_called_once_with(
            organization=self.organization, source="update", is_active=True, starts_at__lte=now,
        )
        queryset.filter.assert_called_once()

    def test_unlisted_anonymous_and_private_feed_do_not_query_entries(self):
        with patch.object(OrganizationFeedEntry, "objects") as manager:
            self.assertEqual(feed_service.visible_feed(self.organization, viewer=self.anonymous), [])
            self.organization.visibility = "private"
            self.assertEqual(feed_service.visible_feed(self.organization, viewer=self.viewer), [])
        manager.filter.assert_not_called()

    def test_media_delivery_follows_the_post_viewer_rules(self):
        asset = SimpleNamespace(
            organization=self.organization, is_ready_for_publication=lambda: True,
            update_usages=MagicMock(),
        )
        asset.update_usages.select_related.return_value = [SimpleNamespace(update=self.update)]
        with patch.object(media_access, "can_manage_media", return_value=False):
            self.assertTrue(media_access.can_deliver_organization_asset(asset=asset, viewer=self.viewer))
            self.assertFalse(media_access.can_deliver_organization_asset(asset=asset, viewer=self.anonymous))
            self.organization.visibility = "private"
            self.assertFalse(media_access.can_deliver_organization_asset(asset=asset, viewer=self.viewer))

    def test_media_safety_and_hold_gates_remain_required(self):
        asset = SimpleNamespace(
            organization=self.organization, is_ready_for_publication=MagicMock(return_value=False),
            update_usages=MagicMock(),
        )
        asset.update_usages.select_related.return_value = [SimpleNamespace(update=self.update)]
        self.assertFalse(media_access.can_deliver_organization_asset(asset=asset, viewer=self.viewer))
        asset.is_ready_for_publication.return_value = True
        self.is_held.return_value = True
        with patch.object(held_content_access, "is_sanctuary_review_admin", return_value=False):
            self.assertFalse(media_access.can_deliver_organization_asset(asset=asset, viewer=self.viewer))

    def request_feed(self, viewer=None):
        request = APIRequestFactory().get("/api/v1/organization-content/test-unlisted/feed/")
        if viewer:
            force_authenticate(request, user=viewer)
        view = feed_views.PublicOrganizationFeedViewSet.as_view(
            {"get": "list"}, authentication_classes=[], throttle_classes=[],
        )
        return view(request, slug=self.organization.slug)

    def test_endpoint_returns_200_for_signed_in_unlisted_visitor(self):
        with (
            patch.object(feed_views, "get_object_or_404", return_value=self.organization) as lookup,
            patch.object(feed_views, "visible_feed", return_value=[]) as visible,
            patch.object(feed_views, "PublicOrganizationFeedEntrySerializer") as serializer,
        ):
            serializer.return_value.data = []
            response = self.request_feed(self.viewer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])
        visible.assert_called_once_with(self.organization, viewer=self.viewer)
        self.assertEqual(lookup.call_args.kwargs["status"], "active")
        self.assertEqual(set(lookup.call_args.kwargs["visibility__in"]), {"public", "unlisted"})

    def test_endpoint_keeps_unlisted_anonymous_requests_hidden(self):
        with (
            patch.object(feed_views, "get_object_or_404", return_value=self.organization),
            patch.object(feed_views, "visible_feed") as visible,
        ):
            response = self.request_feed()
        self.assertEqual(response.status_code, 404)
        visible.assert_not_called()

    def test_endpoint_preserves_existing_anonymous_public_feed(self):
        self.organization.visibility = "public"
        with (
            patch.object(feed_views, "get_object_or_404", return_value=self.organization),
            patch.object(feed_views, "visible_feed", return_value=[]),
            patch.object(feed_views, "PublicOrganizationFeedEntrySerializer") as serializer,
        ):
            serializer.return_value.data = []
            response = self.request_feed()
        self.assertEqual(response.status_code, 200)

    def test_endpoint_keeps_private_and_inactive_organizations_hidden(self):
        for visibility, status in (("private", "active"), ("unlisted", "closed")):
            with self.subTest(visibility=visibility, status=status):
                self.organization.visibility, self.organization.status = visibility, status
                with patch.object(feed_views, "get_object_or_404", return_value=self.organization):
                    self.assertEqual(self.request_feed(self.viewer).status_code, 404)
