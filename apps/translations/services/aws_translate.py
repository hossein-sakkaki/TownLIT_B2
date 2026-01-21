# apps/translations/services/aws_translate.py

import boto3
from django.conf import settings


class AWSTranslateClient:
    """Thin wrapper around AWS Translate."""

    def __init__(self):
        self.client = boto3.client(
            "translate",
            region_name=settings.AWS_REGION,
        )

    def translate(
        self,
        *,
        text: str,
        target_language: str,
        source_language: str | None = None,
    ) -> dict:
        """
        Translate text using AWS Translate.
        Returns dict with translated_text + source_language.
        """

        response = self.client.translate_text(
            Text=text,
            SourceLanguageCode=source_language or "auto",
            TargetLanguageCode=target_language,
        )

        return {
            "translated_text": response["TranslatedText"],
            "source_language": response.get(
                "SourceLanguageCode",
                source_language,
            ),
        }
