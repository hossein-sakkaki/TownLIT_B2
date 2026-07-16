# apps/translations/views/conversation_key_guidance.py

from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.translations.models import (
    ConversationKeyGuidance,
)
from apps.translations.services.base import (
    translate_cached,
)
from apps.translations.services.exceptions import (
    EmptySourceTextError,
)


GUIDANCE_DEFAULTS = {
    ConversationKeyGuidance.Slug.BACKUP: {
        "title": (
            "Protect your private message history"
        ),
        "content": """
TownLIT protects private one-to-one messages with an encryption key stored on your device. This recovery passphrase protects an encrypted backup of that key.

You may need this passphrase when you sign in on a new phone, reinstall the app, or lose access to this device. Restoring the key allows the new device to open older private messages that were encrypted for your previous key.

This is not your TownLIT account password. Choose a separate, strong passphrase and store it somewhere safe. TownLIT does not receive the passphrase and cannot recover or reset it for you.
""".strip(),
    },

    ConversationKeyGuidance.Slug.RESTORE: {
        "title": (
            "Restore access to older private messages"
        ),
        "content": """
This device does not currently have the private encryption key used for your previous one-to-one messages.

Enter the exact recovery passphrase you created when the key backup was saved. TownLIT will use it on this device to decrypt the protected key backup and restore access to older private messages.

This is not your TownLIT account password. An incorrect passphrase will not delete your messages or your backup, but the older encrypted messages will remain unreadable on this device until the correct passphrase is entered.
""".strip(),
    },

    ConversationKeyGuidance.Slug.RESOLVE: {
        "title": (
            "Choose how this device should continue"
        ),
        "content": """
Restoring your existing encryption key is the recommended option because it preserves access to older private messages.

Choose Restore from Backup when you still know your recovery passphrase.

Choose Create New Key only when you no longer have the passphrase or cannot restore the previous key. A new key will protect new private messages, but older messages encrypted with the previous key may remain unreadable on this device.

After creating a new key, TownLIT will ask you to create a new recovery passphrase and back up the new key.
""".strip(),
    },
}


class ConversationKeyGuidanceTranslationViewSet(
    viewsets.ViewSet
):
    """
    Translation endpoint for conversation-key setup guidance.

    POST:
        /translations/conversation-key-guidance/<slug>/translate/
    """

    lookup_field = "slug"
    permission_classes = [AllowAny]

    def get_object(self):
        slug = (
            self.kwargs.get("slug")
            or ""
        ).strip().lower()

        defaults = GUIDANCE_DEFAULTS.get(
            slug
        )

        if defaults is None:
            return get_object_or_404(
                ConversationKeyGuidance,
                slug=slug,
            )

        guidance, _ = (
            ConversationKeyGuidance.objects
            .get_or_create(
                slug=slug,
                defaults=defaults,
            )
        )

        update_fields = []

        expected_title = defaults["title"]
        expected_content = defaults["content"]

        if guidance.title != expected_title:
            guidance.title = expected_title
            update_fields.append(
                "title"
            )

        if guidance.content != expected_content:
            guidance.content = expected_content
            update_fields.append(
                "content"
            )

        if update_fields:
            update_fields.append(
                "updated_at"
            )

            guidance.save(
                update_fields=update_fields
            )

        return guidance

    @action(
        detail=True,
        methods=["post"],
        url_path="translate",
    )
    def translate_guidance(
        self,
        request,
        slug=None,
    ):
        guidance = self.get_object()

        source_title = (
            guidance.title
            or ""
        ).strip()

        source_content = (
            guidance.content
            or ""
        ).strip()

        if (
            not source_title
            or not source_content
        ):
            return Response(
                {
                    "detail": (
                        "Guidance title or content "
                        "is empty."
                    ),
                    "code": "empty_source_text",
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        target_language = request.data.get(
            "target_language"
        )

        try:
            title_result = translate_cached(
                obj=guidance,
                field_name="title",
                user=request.user,
                target_language=target_language,
            )

            content_result = translate_cached(
                obj=guidance,
                field_name="content",
                user=request.user,
                target_language=target_language,
            )

        except EmptySourceTextError:
            return Response(
                {
                    "detail": (
                        "Guidance title or content "
                        "is empty."
                    ),
                    "code": "empty_source_text",
                },
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        return Response(
            {
                "title": title_result["text"],
                "content": content_result["text"],
                "target_language": (
                    content_result[
                        "target_language"
                    ]
                ),
                "cached": (
                    title_result["cached"]
                    and content_result["cached"]
                ),
            },
            status=status.HTTP_200_OK,
        )