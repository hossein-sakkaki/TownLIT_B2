# apps/communication/services/review.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


import hashlib
from collections import Counter
from dataclasses import dataclass

from django.conf import settings
from django.core import signing

from apps.communication.constants import CampaignStatus

from .exceptions import (
    AudienceConfigurationError,
    CampaignRenderError,
)
from .recipients import AudienceResolver
from .rendering import CampaignRenderer
from .suppression import EmailSuppressionService


CONFIRMATION_SALT = (
    "townlit.communication.campaign-confirmation.v1"
)

CONFIRMATION_MAX_AGE_SECONDS = 15 * 60

DEFAULT_STRONG_CONFIRMATION_THRESHOLD = 500


@dataclass(frozen=True)
class CampaignPreflightCheck:
    key: str
    label: str
    state: str
    detail: str


@dataclass(frozen=True)
class CampaignSuppressionSummary:
    reason: str
    label: str
    count: int


@dataclass
class CampaignPreflightReport:
    audience_label: str
    total_recipients: int
    suppressed_recipients: int
    deliverable_recipients: int
    recipient_fingerprint: str
    suppression_reasons: list
    checks: list
    blockers: list
    warnings: list
    can_send: bool


class CampaignPreflightService:
    """
    Build the canonical pre-send campaign review.

    The same audience resolver and suppression service used by
    delivery are reused here so the review cannot drift from send.
    """

    SENDABLE_STATUSES = {
        CampaignStatus.DRAFT,
        CampaignStatus.REVIEW,
        CampaignStatus.READY,
        CampaignStatus.PAUSED,
        CampaignStatus.FAILED,
    }

    def __init__(self):
        self.audience_resolver = AudienceResolver()
        self.suppression_service = (
            EmailSuppressionService()
        )
        self.renderer = CampaignRenderer()

    @property
    def strong_confirmation_threshold(self):
        return int(
            getattr(
                settings,
                "COMMUNICATION_STRONG_CONFIRMATION_THRESHOLD",
                DEFAULT_STRONG_CONFIRMATION_THRESHOLD,
            )
        )

    @staticmethod
    def _normalized_email(recipient):
        return (
            recipient.email
            or ""
        ).strip().lower()
        
    def build(self, campaign):
        checks = []

        self._check_state(
            campaign,
            checks,
        )
        self._check_subject(
            campaign,
            checks,
        )
        self._check_preheader(
            campaign,
            checks,
        )
        self._check_content(
            campaign,
            checks,
        )
        self._check_unsubscribe_policy(
            campaign,
            checks,
        )
        self._check_test_email(
            campaign,
            checks,
        )

        recipients = []
        resolution_error = ""

        try:
            recipients = list(
                self.audience_resolver.resolve_campaign(
                    campaign
                )
            )
        except AudienceConfigurationError as error:
            resolution_error = str(error)

        suppression_counts = Counter()
        suppression_by_email = {}

        if not resolution_error:
            for recipient in recipients:
                reason = (
                    self.suppression_service
                    .get_reason(
                        campaign,
                        recipient,
                    )
                )

                normalized_email = (
                    self._normalized_email(
                        recipient
                    )
                )

                if reason:
                    reason_key = str(reason)

                    suppression_counts[
                        reason_key
                    ] += 1

                    suppression_by_email[
                        normalized_email
                    ] = reason_key
                else:
                    suppression_by_email[
                        normalized_email
                    ] = ""

        total_recipients = len(recipients)
        suppressed_recipients = sum(
            suppression_counts.values()
        )
        deliverable_recipients = max(
            total_recipients
            - suppressed_recipients,
            0,
        )

        if resolution_error:
            checks.append(
                CampaignPreflightCheck(
                    key="audience",
                    label="Audience",
                    state="block",
                    detail=resolution_error,
                )
            )

        elif not total_recipients:
            checks.append(
                CampaignPreflightCheck(
                    key="audience",
                    label="Audience",
                    state="block",
                    detail=(
                        "The selected audience currently "
                        "contains no recipients."
                    ),
                )
            )

        else:
            checks.append(
                CampaignPreflightCheck(
                    key="audience",
                    label="Audience",
                    state="pass",
                    detail=(
                        f"{total_recipients:,} current "
                        "recipient(s) resolved."
                    ),
                )
            )

        if (
            total_recipients
            and not deliverable_recipients
        ):
            checks.append(
                CampaignPreflightCheck(
                    key="deliverability",
                    label="Expected Delivery",
                    state="block",
                    detail=(
                        "Every resolved recipient is "
                        "currently suppressed."
                    ),
                )
            )

        elif deliverable_recipients:
            checks.append(
                CampaignPreflightCheck(
                    key="deliverability",
                    label="Expected Delivery",
                    state="pass",
                    detail=(
                        f"{deliverable_recipients:,} "
                        "recipient(s) are currently "
                        "eligible for delivery."
                    ),
                )
            )

        if suppressed_recipients:
            checks.append(
                CampaignPreflightCheck(
                    key="suppression",
                    label="Suppression",
                    state="warning",
                    detail=(
                        f"{suppressed_recipients:,} "
                        "recipient(s) will be skipped."
                    ),
                )
            )
        elif total_recipients:
            checks.append(
                CampaignPreflightCheck(
                    key="suppression",
                    label="Suppression",
                    state="pass",
                    detail=(
                        "No recipients are currently "
                        "suppressed."
                    ),
                )
            )

        if recipients:
            self._check_rendering(
                campaign,
                recipients[0],
                checks,
            )

        fingerprint = self._recipient_fingerprint(
            recipients,
            suppression_by_email,
        )

        suppression_reasons = [
            CampaignSuppressionSummary(
                reason=reason,
                label=self._reason_label(
                    reason
                ),
                count=count,
            )
            for reason, count in sorted(
                suppression_counts.items(),
                key=lambda item: (
                    -item[1],
                    item[0],
                ),
            )
        ]

        blockers = [
            check
            for check in checks
            if check.state == "block"
        ]

        warnings = [
            check
            for check in checks
            if check.state == "warning"
        ]

        return CampaignPreflightReport(
            audience_label=(
                self._audience_label(
                    campaign
                )
            ),
            total_recipients=total_recipients,
            suppressed_recipients=(
                suppressed_recipients
            ),
            deliverable_recipients=(
                deliverable_recipients
            ),
            recipient_fingerprint=(
                fingerprint
            ),
            suppression_reasons=(
                suppression_reasons
            ),
            checks=checks,
            blockers=blockers,
            warnings=warnings,
            can_send=not blockers,
        )

    def make_confirmation_token(
        self,
        *,
        campaign,
        report,
        action,
    ):
        payload = {
            "campaign_id": campaign.pk,
            "action": action,
            "content_version": (
                campaign.content_version
            ),
            "deliverable_recipients": (
                report.deliverable_recipients
            ),
            "recipient_fingerprint": (
                report.recipient_fingerprint
            ),
            "scheduled_time": (
                campaign.scheduled_time.isoformat()
                if campaign.scheduled_time
                else ""
            ),
            "schedule_timezone": (
                campaign.schedule_timezone
                or ""
            ),
        }

        return signing.dumps(
            payload,
            salt=CONFIRMATION_SALT,
            compress=True,
        )

    def validate_confirmation_token(
        self,
        *,
        token,
        campaign,
        report,
        action,
    ):
        if not token:
            return False

        try:
            payload = signing.loads(
                token,
                salt=CONFIRMATION_SALT,
                max_age=(
                    CONFIRMATION_MAX_AGE_SECONDS
                ),
            )
        except signing.BadSignature:
            return False

        expected = {
            "campaign_id": campaign.pk,
            "action": action,
            "content_version": (
                campaign.content_version
            ),
            "deliverable_recipients": (
                report.deliverable_recipients
            ),
            "recipient_fingerprint": (
                report.recipient_fingerprint
            ),
            "scheduled_time": (
                campaign.scheduled_time.isoformat()
                if campaign.scheduled_time
                else ""
            ),
            "schedule_timezone": (
                campaign.schedule_timezone
                or ""
            ),
        }

        return payload == expected

    @classmethod
    def has_renderable_content(
        cls,
        campaign,
    ):
        if not campaign:
            return False

        if campaign.custom_html:
            return True

        if campaign.content_blocks.filter(
            is_enabled=True
        ).exists():
            return True

        if not campaign.template_id:
            return False

        if campaign.template.body_template:
            return True

        return (
            campaign.template
            .content_blocks
            .filter(is_enabled=True)
            .exists()
        )

    def _check_state(
        self,
        campaign,
        checks,
    ):
        if (
            campaign.status
            in self.SENDABLE_STATUSES
        ):
            checks.append(
                CampaignPreflightCheck(
                    key="state",
                    label="Campaign State",
                    state="pass",
                    detail=(
                        campaign.get_status_display()
                    ),
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="state",
                label="Campaign State",
                state="block",
                detail=(
                    "This campaign is already in a "
                    "delivery or terminal state."
                ),
            )
        )

    def _check_subject(
        self,
        campaign,
        checks,
    ):
        if (campaign.subject or "").strip():
            checks.append(
                CampaignPreflightCheck(
                    key="subject",
                    label="Subject",
                    state="pass",
                    detail=campaign.subject,
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="subject",
                label="Subject",
                state="block",
                detail="A subject line is required.",
            )
        )

    def _check_preheader(
        self,
        campaign,
        checks,
    ):
        if (
            campaign.preheader_text
            or ""
        ).strip():
            checks.append(
                CampaignPreflightCheck(
                    key="preheader",
                    label="Preheader",
                    state="pass",
                    detail=(
                        campaign.preheader_text
                    ),
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="preheader",
                label="Preheader",
                state="warning",
                detail=(
                    "No preheader is configured. "
                    "The campaign can still be sent."
                ),
            )
        )

    def _check_content(
        self,
        campaign,
        checks,
    ):
        if self.has_renderable_content(
            campaign
        ):
            checks.append(
                CampaignPreflightCheck(
                    key="content",
                    label="Content",
                    state="pass",
                    detail=(
                        "Campaign has renderable "
                        "email content."
                    ),
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="content",
                label="Content",
                state="block",
                detail=(
                    "Add campaign or template "
                    "content before sending."
                ),
            )
        )

    def _check_unsubscribe_policy(
        self,
        campaign,
        checks,
    ):
        if campaign.ignore_unsubscribe:
            checks.append(
                CampaignPreflightCheck(
                    key="unsubscribe",
                    label="Unsubscribe Protection",
                    state="warning",
                    detail=(
                        "Unsubscribe suppression is "
                        "explicitly bypassed for this "
                        "campaign."
                    ),
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="unsubscribe",
                label="Unsubscribe Protection",
                state="pass",
                detail=(
                    "Recipient preferences will "
                    "be respected."
                ),
            )
        )

    def _check_test_email(
        self,
        campaign,
        checks,
    ):
        if campaign.has_current_test:
            checks.append(
                CampaignPreflightCheck(
                    key="test",
                    label="Test Email",
                    state="pass",
                    detail=(
                        "Current campaign version "
                        f"was tested using "
                        f"{campaign.last_test_email}."
                    ),
                )
            )
            return

        if campaign.last_test_sent_at:
            detail = (
                "A test was sent previously, but "
                "the campaign has changed since "
                "that test."
            )
        else:
            detail = (
                "A test email has not been sent "
                "for the current campaign."
            )

        checks.append(
            CampaignPreflightCheck(
                key="test",
                label="Test Email",
                state="warning",
                detail=detail,
            )
        )

    def _check_rendering(
        self,
        campaign,
        recipient,
        checks,
    ):
        try:
            rendered = self.renderer.render(
                campaign=campaign,
                recipient=recipient,
                preview=True,
            )

            if not rendered.body_html.strip():
                raise CampaignRenderError(
                    "Rendered body is empty."
                )

        except CampaignRenderError as error:
            checks.append(
                CampaignPreflightCheck(
                    key="rendering",
                    label="Rendering",
                    state="block",
                    detail=str(error),
                )
            )
            return

        checks.append(
            CampaignPreflightCheck(
                key="rendering",
                label="Rendering",
                state="pass",
                detail=(
                    "Campaign rendered "
                    "successfully."
                ),
            )
        )

    def _recipient_fingerprint(
        self,
        recipients,
        suppression_by_email,
    ):
        digest = hashlib.sha256()

        ordered = sorted(
            recipients,
            key=self._normalized_email,
        )

        for recipient in ordered:
            email = self._normalized_email(
                recipient
            )
            reason = (
                suppression_by_email.get(
                    email,
                    "",
                )
            )

            digest.update(
                email.encode("utf-8")
            )
            digest.update(b"|")
            digest.update(
                reason.encode("utf-8")
            )
            digest.update(b"\n")

        return digest.hexdigest()

    def _audience_label(
        self,
        campaign,
    ):
        if campaign.recipients.exists():
            return "Specific Recipients"

        if campaign.audience_id:
            return campaign.audience.name

        return (
            campaign.get_target_group_display()
        )

    def _reason_label(
        self,
        reason,
    ):
        return (
            reason.replace("_", " ")
            .replace("-", " ")
            .strip()
            .title()
        )