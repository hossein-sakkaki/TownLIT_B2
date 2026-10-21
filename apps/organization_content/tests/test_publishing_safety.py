# apps/organization_content/tests/test_publishing_safety.py
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-19.
# Last Update by Hossein Sakkaki on 2026-10-19.

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from apps.organization_content import publishing_policy
from apps.organization_content.models import OrganizationUpdate
from apps.organization_content.services import content_safety, updates
from apps.organization_content.services.access import ensure_update_revision
from apps.organization_media.models import OrganizationMediaAsset
from validators.mediaValidators.ugc_policies import MOMENT_VIDEO_POLICY


class PublishingPolicyTests(SimpleTestCase):
    def test_supported_media_combinations(self):
        for kinds in ([], ["image"], ["image"] * 7, ["video"]):
            with self.subTest(kinds=kinds):
                publishing_policy.validate_media_selection([SimpleNamespace(kind=k) for k in kinds])

    def test_invalid_media_combinations(self):
        for kinds in (["image"] * 8, ["video", "image"], ["video", "video"], ["audio"]):
            with self.subTest(kinds=kinds), self.assertRaises(ValidationError):
                publishing_policy.validate_media_selection([SimpleNamespace(kind=k) for k in kinds])

    def test_existing_video_policy_is_reused(self):
        self.assertIs(publishing_policy.VIDEO_POLICY, MOMENT_VIDEO_POLICY)
        self.assertEqual(publishing_policy.MAX_IMAGE_BYTES, 14 * 1024 * 1024)
        self.assertEqual(publishing_policy.upload_policy_payload()["max_photos"], 7)

    def test_caption_is_required_and_bounded(self):
        self.assertEqual(updates._normalize_caption("  Welcome  "), "Welcome")
        for value in ("   ", "word " * 2501):
            with self.subTest(value_length=len(value)), self.assertRaises(ValidationError):
                updates._normalize_caption(value)
        self.assertEqual(len(updates._normalize_caption("word " * 2500).split()), 2500)


class CaptionSafetyTests(SimpleTestCase):
    @patch.object(content_safety, "enforce_text_safety")
    def test_shared_safety_receives_caption_and_actor(self, enforce):
        actor = object()
        content_safety.enforce_update_caption_safety(caption="Welcome", actor=actor)
        self.assertEqual(enforce.call_args.kwargs["text"], "Welcome")
        self.assertIs(enforce.call_args.kwargs["actor"], actor)
        self.assertEqual(enforce.call_args.kwargs["field_name"], "caption")

    @patch.object(content_safety, "enforce_text_safety")
    def test_unchanged_verified_caption_avoids_duplicate_provider_work(self, enforce):
        content_safety.enforce_update_caption_safety(
            caption="Welcome", actor=object(), instance=SimpleNamespace(caption="Welcome"),
        )
        enforce.assert_not_called()

    @patch.object(content_safety, "enforce_text_safety", side_effect=ValidationError("Blocked"))
    def test_safety_failure_propagates(self, enforce):
        with self.assertRaises(ValidationError):
            content_safety.enforce_update_caption_safety(caption="Rejected", actor=object())


class AssetResolutionTests(SimpleTestCase):
    def setUp(self):
        self.organization = SimpleNamespace(pk=17)
        self.asset = MagicMock(public_id="asset-1", status="processing", kind="image")
        self.asset.is_ready_for_publication.return_value = False

    @patch.object(OrganizationMediaAsset, "objects")
    def test_draft_can_retain_pending_media(self, manager):
        manager.filter.return_value = [self.asset]
        result = updates._resolve_assets(organization=self.organization, public_ids=["asset-1"], allow_pending=True)
        self.assertEqual(result, [self.asset])
        self.assertIs(manager.filter.call_args.kwargs["organization"], self.organization)

    @patch.object(OrganizationMediaAsset, "objects")
    def test_published_content_rejects_pending_media(self, manager):
        manager.filter.return_value = [self.asset]
        with self.assertRaises(ValidationError):
            updates._resolve_assets(organization=self.organization, public_ids=["asset-1"])

    @patch.object(OrganizationMediaAsset, "objects")
    def test_unknown_or_foreign_asset_is_rejected(self, manager):
        manager.filter.return_value = []
        with self.assertRaises(ValidationError):
            updates._resolve_assets(organization=self.organization, public_ids=["foreign"], allow_pending=True)

    @patch.object(OrganizationMediaAsset, "objects")
    def test_order_is_preserved_and_duplicate_links_removed(self, manager):
        second = MagicMock(public_id="asset-2", status="ready", kind="image")
        manager.filter.return_value = [second, self.asset]
        self.assertEqual(updates._resolve_assets(
            organization=self.organization, public_ids=["asset-1", "asset-2", "asset-1"], allow_pending=True,
        ), [self.asset, second])


class PublicationGateTests(SimpleTestCase):
    def setUp(self):
        self.update = MagicMock()
        self.update.Status = OrganizationUpdate.Status
        self.update.pk = 9
        self.update.status = OrganizationUpdate.Status.DRAFT
        self.update.is_active = True
        self.update.is_suspended = False
        self.update.caption = "Welcome"
        self.update.updated_at = timezone.now()
        self.update.media_items.select_related.return_value = []
        manager = self.patch_attribute(OrganizationUpdate, "objects")
        manager.select_for_update.return_value.select_related.return_value.get.return_value = self.update
        for name in ("ensure_organization_content_writes_enabled", "_ensure_manager", "_audit", "set_home_visibility", "enforce_update_caption_safety"):
            self.patch_attribute(updates, name)
        held = patch("apps.sanctuary.services.held_content_access.is_under_active_safety_hold", return_value=False)
        held.start()
        self.addCleanup(held.stop)

    def patch_attribute(self, target, name):
        patcher = patch.object(target, name)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def publish(self, **kwargs):
        # These are service unit tests; database transaction behavior is separate.
        return updates.publish_update.__wrapped__(update=self.update, actor=object(), **kwargs)

    def test_text_only_content_can_publish(self):
        result = self.publish(expected_updated_at=self.update.updated_at)
        self.assertEqual(result.status, "published")
        self.assertTrue(result.caption_safety_verified)
        updates.enforce_update_caption_safety.assert_called_once()

    def test_pending_asset_prevents_publication(self):
        asset = MagicMock(kind="video")
        asset.is_ready_for_publication.return_value = False
        self.update.media_items.select_related.return_value = [SimpleNamespace(asset=asset)]
        with self.assertRaises(ValidationError):
            self.publish()
        self.update.save.assert_not_called()
        updates.set_home_visibility.assert_not_called()

    def test_stale_revision_prevents_publication(self):
        with self.assertRaises(ValidationError):
            self.publish(expected_updated_at=self.update.updated_at - timedelta(seconds=1))
        self.update.save.assert_not_called()

    def test_suspended_content_prevents_publication(self):
        self.update.is_suspended = True
        with self.assertRaises(ValidationError):
            self.publish()

    def test_archived_content_prevents_publication(self):
        self.update.status = OrganizationUpdate.Status.ARCHIVED
        with self.assertRaises(ValidationError):
            self.publish()

    def test_repeat_publish_is_idempotent(self):
        self.update.status = OrganizationUpdate.Status.PUBLISHED
        self.assertIs(self.publish(), self.update)
        self.update.save.assert_not_called()
        updates._audit.assert_not_called()

    def test_revision_comparison_accepts_only_current_version(self):
        ensure_update_revision(update=self.update, expected_updated_at=self.update.updated_at)
        with self.assertRaises(ValidationError):
            ensure_update_revision(update=self.update, expected_updated_at=timezone.now() + timedelta(seconds=1))


    def test_active_sanctuary_hold_prevents_publication(self):
        with patch("apps.sanctuary.services.held_content_access.is_under_active_safety_hold", return_value=True):
            with self.assertRaises(ValidationError):
                self.publish()
        self.update.save.assert_not_called()

    def test_caption_safety_failure_prevents_persistence(self):
        updates.enforce_update_caption_safety.side_effect = ValidationError("Review required")
        with self.assertRaises(ValidationError):
            self.publish()
        self.update.save.assert_not_called()
        updates.set_home_visibility.assert_not_called()


class ContentPermissionTests(SimpleTestCase):
    def test_either_existing_content_permission_is_accepted(self):
        from apps.organization_content.services import access
        from apps.organizations.constants import OrganizationPermissionKey
        for granted in (OrganizationPermissionKey.MANAGE_CONTENT, OrganizationPermissionKey.MANAGE_ANNOUNCEMENTS):
            with self.subTest(granted=granted), patch.object(access, "user_has_organization_permission") as check:
                check.side_effect = lambda **kwargs: kwargs["permission_key"] == granted
                self.assertTrue(access.can_manage_content(actor=object(), organization=SimpleNamespace(status="active")))

    def test_inactive_organization_is_rejected(self):
        from apps.organization_content.services import access
        with patch.object(access, "user_has_organization_permission", return_value=True) as check:
            self.assertFalse(access.can_manage_content(actor=object(), organization=SimpleNamespace(status="suspended")))
            check.assert_not_called()

    def test_missing_permission_is_rejected(self):
        from apps.organization_content.services import access
        with patch.object(access, "user_has_organization_permission", return_value=False):
            self.assertFalse(access.can_manage_content(actor=object(), organization=SimpleNamespace(status="active")))
