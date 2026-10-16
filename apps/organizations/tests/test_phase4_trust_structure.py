# apps/organizations/tests/test_phase4_trust_structure.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.
#

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.organizations.constants import (
    OrganizationKind,
    OrganizationStatus,
    OrganizationVerificationDocumentType,
    OrganizationVerificationStatus,
    OrganizationVisibility,
)
from apps.organizations.models import (
    Organization,
    OrganizationVerificationCase,
    OrganizationVerificationDocument,
)
from apps.organizations.services.verification import (
    deactivate_verification_document,
    update_verification_case,
)
from apps.organizations.views.hierarchy import OrganizationRelationshipCandidatesView
from apps.subscriptions.models import SubscriptionAccount


@override_settings(
    TOWNLIT_ORGANIZATIONS_ENABLED=True,
    TOWNLIT_ORGANIZATIONS_VERIFICATION_ENABLED=True,
    TOWNLIT_ORGANIZATIONS_HIERARCHY_ENABLED=True,
)
class OrganizationPhase4TrustStructureTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff = user_model.objects.create_user(
            email="phase4-staff@townlit.test",
            password="test-password",
        )
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

        self.organization = self._create_organization(
            name="Phase Four Organization",
            slug="phase-four-organization",
        )

    def _create_organization(self, *, name, slug, visibility=OrganizationVisibility.PUBLIC):
        account = SubscriptionAccount.objects.create()
        return Organization.objects.create(
            name=name,
            slug=slug,
            kind=OrganizationKind.NONPROFIT,
            subscription_account=account,
            status=OrganizationStatus.ACTIVE,
            visibility=visibility,
        )

    def test_verification_case_can_be_edited_only_in_editable_states(self):
        verification_case = OrganizationVerificationCase.objects.create(
            organization=self.organization,
            status=OrganizationVerificationStatus.DRAFT,
        )

        updated = update_verification_case(
            verification_case=verification_case,
            actor=self.staff,
            validated_data={
                "legal_name": "TownLIT Phase Four Society",
                "jurisdiction_country": "CA",
            },
        )

        self.assertEqual(
            updated.legal_name,
            "TownLIT Phase Four Society",
        )
        self.assertEqual(updated.jurisdiction_country, "CA")

        verification_case.status = OrganizationVerificationStatus.UNDER_REVIEW
        verification_case.save(update_fields=["status"])

        with self.assertRaises(ValidationError):
            update_verification_case(
                verification_case=verification_case,
                actor=self.staff,
                validated_data={"legal_name": "Should Not Save"},
            )

    def test_verification_document_deactivation_preserves_record(self):
        verification_case = OrganizationVerificationCase.objects.create(
            organization=self.organization,
            status=OrganizationVerificationStatus.NEEDS_INFORMATION,
        )
        document = OrganizationVerificationDocument.objects.create(
            verification_case=verification_case,
            document_type=OrganizationVerificationDocumentType.INCORPORATION,
            file="organizations/verification/test.pdf",
            uploaded_by=self.staff,
        )

        deactivate_verification_document(
            document=document,
            actor=self.staff,
        )

        document.refresh_from_db()
        self.assertFalse(document.is_active)
        self.assertTrue(
            OrganizationVerificationDocument.objects.filter(pk=document.pk).exists()
        )

    def test_relationship_candidate_search_is_public_active_and_excludes_self(self):
        visible = self._create_organization(
            name="Visible Network",
            slug="visible-network",
        )
        self._create_organization(
            name="Hidden Network",
            slug="hidden-network",
            visibility=OrganizationVisibility.PRIVATE,
        )

        request = APIRequestFactory().get(
            "/organizations/phase-four-organization/relationships/candidates/",
            {"q": "network"},
        )
        force_authenticate(request, user=self.staff)

        response = OrganizationRelationshipCandidatesView.as_view()(
            request,
            slug=self.organization.slug,
        )

        self.assertEqual(response.status_code, 200)
        returned_slugs = {item["slug"] for item in response.data}
        self.assertIn(visible.slug, returned_slugs)
        self.assertNotIn("hidden-network", returned_slugs)
        self.assertNotIn(self.organization.slug, returned_slugs)
