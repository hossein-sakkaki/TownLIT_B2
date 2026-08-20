# apps/communication/services/preference_tokens.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.core import signing
from django.contrib.auth import get_user_model

from apps.moderation.models import AccessRequest
from utils.email.token_generator import validate_email_opt_token


CustomUser = get_user_model()

TOKEN_SALT = "townlit.communication.preference.v2"
TOKEN_VERSION = 2

ACTION_UNSUBSCRIBE = "unsubscribe"
ACTION_RESUBSCRIBE = "resubscribe"

SUBJECT_USER = "user"
SUBJECT_EXTERNAL = "external_contact"
SUBJECT_ACCESS_REQUEST = "access_request"


class EmailPreferenceTokenService:
    """
    Signed campaign preference tokens.

    New tokens explicitly identify recipient type, campaign and topic.
    Legacy unsubscribe tokens remain readable for old emails.
    """

    def generate_for_recipient(self, *, campaign, recipient, action):
        subject_type, subject_id = self._recipient_identity(recipient)

        return self.generate(
            action=action,
            email=recipient.email,
            subject_type=subject_type,
            subject_id=subject_id,
            campaign_id=campaign.id,
            topic_id=campaign.topic_id,
        )

    def generate(
        self,
        *,
        action,
        email,
        subject_type,
        subject_id=None,
        campaign_id=None,
        topic_id=None,
    ):
        if action not in {ACTION_UNSUBSCRIBE, ACTION_RESUBSCRIBE}:
            raise ValueError("Unsupported email preference action.")

        payload = {
            "v": TOKEN_VERSION,
            "action": action,
            "email": (email or "").strip().lower(),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "campaign_id": campaign_id,
            "topic_id": topic_id,
        }

        return signing.dumps(
            payload,
            salt=TOKEN_SALT,
            compress=True,
        )

    def load(self, token, *, expected_action):
        """
        Load a v2 token or fall back to a legacy TownLIT opt token.
        """

        try:
            payload = signing.loads(
                token,
                salt=TOKEN_SALT,
            )

            if payload.get("v") != TOKEN_VERSION:
                raise signing.BadSignature("Unsupported token version.")

            if payload.get("action") != expected_action:
                raise signing.BadSignature("Invalid token action.")

            if not payload.get("email"):
                raise signing.BadSignature("Token has no email address.")

            return payload

        except signing.BadSignature:
            return self._load_legacy(
                token,
                expected_action=expected_action,
            )

    def _load_legacy(self, token, *, expected_action):
        subject = validate_email_opt_token(token)

        if not subject:
            raise signing.BadSignature("Invalid or expired token.")

        if isinstance(subject, CustomUser):
            subject_type = SUBJECT_USER
        elif isinstance(subject, AccessRequest):
            subject_type = SUBJECT_ACCESS_REQUEST
        else:
            raise signing.BadSignature("Unsupported legacy recipient.")

        return {
            "v": 1,
            "action": expected_action,
            "email": (subject.email or "").strip().lower(),
            "subject_type": subject_type,
            "subject_id": subject.id,
            "campaign_id": None,
            "topic_id": None,
        }

    def _recipient_identity(self, recipient):
        if recipient.user:
            return SUBJECT_USER, recipient.user.id

        if recipient.external_contact:
            return SUBJECT_EXTERNAL, recipient.external_contact.id

        if recipient.legacy_access_request:
            return SUBJECT_ACCESS_REQUEST, recipient.legacy_access_request.id

        return "email", None