# apps/organizations/tests/test_admin_verification_private_files.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-13.
# Last Update by Hossein Sakkaki on 2026-10-13.
#

from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase, override_settings

from apps.organizations.admin.private_files import (
    build_verification_document_url,
)


class VerificationAdminPrivateFileURLTests(SimpleTestCase):
    @override_settings(
        ORGANIZATION_VERIFICATION_ADMIN_URL_TTL_SECONDS=300,
    )
    def test_s3_storage_uses_direct_presigned_get_object(self):
        client = Mock()
        client.generate_presigned_url.return_value = (
            "https://signed.example/private-document"
        )

        storage = SimpleNamespace(
            bucket_name="townlit-private",
            connection=SimpleNamespace(
                meta=SimpleNamespace(client=client),
            ),
            url=Mock(return_value="https://unsigned.example/file.pdf"),
        )
        field_file = SimpleNamespace(
            name="organizations/verification/org/certificate.pdf",
            storage=storage,
        )

        url = build_verification_document_url(field_file)

        self.assertEqual(
            url,
            "https://signed.example/private-document",
        )
        storage.url.assert_not_called()
        client.generate_presigned_url.assert_called_once()

        _, kwargs = client.generate_presigned_url.call_args
        self.assertEqual(kwargs["ExpiresIn"], 300)
        self.assertEqual(kwargs["HttpMethod"], "GET")
        self.assertEqual(
            kwargs["Params"]["Bucket"],
            "townlit-private",
        )
        self.assertEqual(
            kwargs["Params"]["Key"],
            "organizations/verification/org/certificate.pdf",
        )
        self.assertTrue(
            kwargs["Params"]["ResponseContentDisposition"].startswith(
                "inline;"
            )
        )

    def test_download_uses_attachment_disposition(self):
        client = Mock()
        client.generate_presigned_url.return_value = "https://signed.example/x"
        storage = SimpleNamespace(
            bucket_name="townlit-private",
            connection=SimpleNamespace(
                meta=SimpleNamespace(client=client),
            ),
        )
        field_file = SimpleNamespace(
            name="organizations/verification/id-card.png",
            storage=storage,
        )

        build_verification_document_url(
            field_file,
            attachment=True,
        )

        _, kwargs = client.generate_presigned_url.call_args
        self.assertTrue(
            kwargs["Params"]["ResponseContentDisposition"].startswith(
                "attachment;"
            )
        )

    def test_non_s3_storage_falls_back_to_storage_url(self):
        storage = SimpleNamespace(
            url=Mock(return_value="/media/private/document.pdf"),
        )
        field_file = SimpleNamespace(
            name="private/document.pdf",
            storage=storage,
        )

        url = build_verification_document_url(field_file)

        self.assertEqual(url, "/media/private/document.pdf")
        storage.url.assert_called_once_with("private/document.pdf")
