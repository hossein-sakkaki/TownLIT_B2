# apps/communication/services/preferences.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.communication.constants import (
    EmailSubscriptionSource,
    EmailSubscriptionStatus,
    EmailUnsubscribeScope,
)
from apps.communication.models import (
    EmailCampaign,
    EmailLog,
    EmailSubscriptionPreference,
    EmailTopic,
    ExternalContact,
    UnsubscribedUser,
)
from apps.moderation.models import AccessRequest

from .analytics import EmailAnalyticsService
from .preference_tokens import (
    ACTION_RESUBSCRIBE,
    ACTION_UNSUBSCRIBE,
    SUBJECT_ACCESS_REQUEST,
    SUBJECT_EXTERNAL,
    SUBJECT_USER,
    EmailPreferenceTokenService,
)


CustomUser = get_user_model()


@dataclass(frozen=True)
class PreferenceActionResult:
    email: str
    user: object = None
    external_contact: object = None
    campaign: object = None
    topic: object = None
    resubscribe_token: str = ""


class EmailPreferenceService:
    """
    Apply global or topic-level subscription preferences.
    """

    def __init__(self):
        self.token_service = EmailPreferenceTokenService()
        self.analytics_service = EmailAnalyticsService()

    @transaction.atomic
    def unsubscribe(self, token, *, request=None):
        payload = self.token_service.load(
            token,
            expected_action=ACTION_UNSUBSCRIBE,
        )

        resolved = self._resolve(payload)

        if resolved.topic and resolved.topic.allow_unsubscribe:
            self._unsubscribe_topic(resolved)
        else:
            self._unsubscribe_global(resolved)

        self._record_unsubscribe(
            resolved,
            request=request,
        )

        resubscribe_token = self.token_service.generate(
            action=ACTION_RESUBSCRIBE,
            email=resolved.email,
            subject_type=payload.get("subject_type"),
            subject_id=payload.get("subject_id"),
            campaign_id=payload.get("campaign_id"),
            topic_id=payload.get("topic_id"),
        )

        return PreferenceActionResult(
            email=resolved.email,
            user=resolved.user,
            external_contact=resolved.external_contact,
            campaign=resolved.campaign,
            topic=resolved.topic,
            resubscribe_token=resubscribe_token,
        )

    @transaction.atomic
    def resubscribe(self, token):
        payload = self.token_service.load(
            token,
            expected_action=ACTION_RESUBSCRIBE,
        )

        resolved = self._resolve(payload)

        if resolved.topic and resolved.topic.allow_unsubscribe:
            self._resubscribe_topic(resolved)
        else:
            self._resubscribe_global(resolved)

        return resolved

    def unsubscribe_legacy_external(self, contact):
        email = (contact.email or "").strip().lower()

        contact.is_unsubscribed = True
        contact.save(update_fields=["is_unsubscribed"])

        self._set_global_unsubscribe(
            email=email,
            user=None,
            source="legacy_external_link",
        )

    def _unsubscribe_topic(self, resolved):
        EmailSubscriptionPreference.objects.update_or_create(
            email=resolved.email,
            topic=resolved.topic,
            defaults={
                "user": resolved.user,
                "status": EmailSubscriptionStatus.UNSUBSCRIBED,
                "source": EmailSubscriptionSource.EMAIL_LINK,
                "unsubscribed_at": timezone.now(),
                "subscribed_at": None,
            },
        )

    def _resubscribe_topic(self, resolved):
        EmailSubscriptionPreference.objects.update_or_create(
            email=resolved.email,
            topic=resolved.topic,
            defaults={
                "user": resolved.user,
                "status": EmailSubscriptionStatus.SUBSCRIBED,
                "source": EmailSubscriptionSource.EMAIL_LINK,
                "subscribed_at": timezone.now(),
                "unsubscribed_at": None,
            },
        )

    def _unsubscribe_global(self, resolved):
        self._set_global_unsubscribe(
            email=resolved.email,
            user=resolved.user,
            source="email_link",
        )

        if resolved.external_contact:
            resolved.external_contact.is_unsubscribed = True
            resolved.external_contact.save(
                update_fields=["is_unsubscribed"]
            )

    def _set_global_unsubscribe(self, *, email, user, source):
        query = Q(email__iexact=email)

        if user:
            query |= Q(user=user)

        record = UnsubscribedUser.objects.filter(query).first()

        if record:
            record.email = email
            record.user = user or record.user
            record.scope = EmailUnsubscribeScope.MARKETING
            record.source = source
            record.unsubscribed_at = timezone.now()
            record.save()
            return record

        return UnsubscribedUser.objects.create(
            email=email,
            user=user,
            scope=EmailUnsubscribeScope.MARKETING,
            source=source,
        )

    def _resubscribe_global(self, resolved):
        query = Q(email__iexact=resolved.email)

        if resolved.user:
            query |= Q(user=resolved.user)

        UnsubscribedUser.objects.filter(query).delete()

        if resolved.external_contact:
            resolved.external_contact.is_unsubscribed = False
            resolved.external_contact.save(
                update_fields=["is_unsubscribed"]
            )

    def _record_unsubscribe(self, resolved, *, request):
        if not resolved.campaign:
            return

        delivery = EmailLog.objects.filter(
            campaign=resolved.campaign,
            email__iexact=resolved.email,
        ).order_by("-id").first()

        if not delivery:
            return

        self.analytics_service.record_unsubscribe(
            delivery_id=delivery.id,
            request=request,
        )

    def _resolve(self, payload):
        subject_type = payload.get("subject_type")
        subject_id = payload.get("subject_id")

        user = None
        external_contact = None

        if subject_type == SUBJECT_USER and subject_id:
            user = CustomUser.objects.filter(pk=subject_id).first()

        elif subject_type == SUBJECT_EXTERNAL and subject_id:
            external_contact = ExternalContact.objects.filter(
                pk=subject_id
            ).first()

        elif subject_type == SUBJECT_ACCESS_REQUEST and subject_id:
            AccessRequest.objects.filter(pk=subject_id).first()

        email = (payload.get("email") or "").strip().lower()

        if user and user.email:
            email = user.email.strip().lower()

        if external_contact and external_contact.email:
            email = external_contact.email.strip().lower()

        if not email:
            raise ValueError("Unable to resolve recipient email.")

        campaign = None
        topic = None

        if payload.get("campaign_id"):
            campaign = EmailCampaign.objects.filter(
                pk=payload["campaign_id"]
            ).first()

        if payload.get("topic_id"):
            topic = EmailTopic.objects.filter(
                pk=payload["topic_id"]
            ).first()

        return PreferenceActionResult(
            email=email,
            user=user,
            external_contact=external_contact,
            campaign=campaign,
            topic=topic,
        )