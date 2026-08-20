# apps/communication/services/analytics.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-20.
# Last Update by Hossein Sakkaki on 2026-08-20.


from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.communication.constants import EmailEventType
from apps.communication.models import (
    EmailCampaign,
    EmailCampaignDailyMetric,
    EmailEvent,
    EmailLog,
)


class EmailAnalyticsService:
    """
    Record recipient engagement without storing raw IP addresses.
    """

    @transaction.atomic
    def record_open(self, *, delivery_id, request=None):
        delivery = EmailLog.objects.select_for_update().get(pk=delivery_id)
        now = timezone.now()
        first_open = not delivery.opened

        delivery.opened = True
        delivery.opened_at = delivery.opened_at or now
        delivery.open_count += 1
        delivery.last_event_at = now
        delivery.save(update_fields=[
            "opened",
            "opened_at",
            "open_count",
            "last_event_at",
        ])

        EmailEvent.objects.create(
            delivery=delivery,
            event_type=EmailEventType.OPENED,
            occurred_at=now,
            user_agent=self._user_agent(request),
            ip_hash=self._ip_hash(request),
        )

        EmailCampaign.objects.filter(pk=delivery.campaign_id).update(
            open_count=F("open_count") + 1,
            unique_open_count=F("unique_open_count") + (1 if first_open else 0),
        )

        self._increment_daily(
            campaign_id=delivery.campaign_id,
            field="opens",
            unique_field="unique_opens" if first_open else None,
        )

        return delivery

    @transaction.atomic
    def record_click(self, *, delivery_id, url, request=None):
        delivery = EmailLog.objects.select_for_update().get(pk=delivery_id)
        now = timezone.now()
        first_click = not delivery.clicked

        delivery.clicked = True
        delivery.clicked_at = delivery.clicked_at or now
        delivery.click_count += 1
        delivery.last_event_at = now
        delivery.save(update_fields=[
            "clicked",
            "clicked_at",
            "click_count",
            "last_event_at",
        ])

        EmailEvent.objects.create(
            delivery=delivery,
            event_type=EmailEventType.CLICKED,
            occurred_at=now,
            url=(url or "")[:2000],
            user_agent=self._user_agent(request),
            ip_hash=self._ip_hash(request),
        )

        EmailCampaign.objects.filter(pk=delivery.campaign_id).update(
            click_count=F("click_count") + 1,
            unique_click_count=F("unique_click_count") + (1 if first_click else 0),
        )

        self._increment_daily(
            campaign_id=delivery.campaign_id,
            field="clicks",
            unique_field="unique_clicks" if first_click else None,
        )

        return delivery

    @transaction.atomic
    def record_unsubscribe(self, *, delivery_id, request=None):
        delivery = EmailLog.objects.select_for_update().get(pk=delivery_id)
        dedupe_key = f"unsubscribe:{delivery.id}"

        event, created = EmailEvent.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "delivery": delivery,
                "event_type": EmailEventType.UNSUBSCRIBED,
                "occurred_at": timezone.now(),
                "user_agent": self._user_agent(request),
                "ip_hash": self._ip_hash(request),
            },
        )

        if not created:
            return False

        EmailCampaign.objects.filter(pk=delivery.campaign_id).update(
            unsubscribe_count=F("unsubscribe_count") + 1,
        )

        self._increment_daily(
            campaign_id=delivery.campaign_id,
            field="unsubscribes",
        )

        return True

    def _increment_daily(self, *, campaign_id, field, unique_field=None):
        metric, _ = EmailCampaignDailyMetric.objects.get_or_create(
            campaign_id=campaign_id,
            date=timezone.localdate(),
        )

        updates = {
            field: F(field) + 1,
        }

        if unique_field:
            updates[unique_field] = F(unique_field) + 1

        EmailCampaignDailyMetric.objects.filter(pk=metric.pk).update(**updates)

    def _user_agent(self, request):
        if not request:
            return ""

        return request.META.get("HTTP_USER_AGENT", "")[:2000]

    def _ip_hash(self, request):
        if not request:
            return ""

        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = forwarded.split(",", 1)[0].strip() if forwarded else ""
        ip = ip or request.META.get("REMOTE_ADDR", "")

        if not ip:
            return ""

        return salted_hmac(
            "communication-email-ip",
            ip,
            secret=settings.SECRET_KEY,
        ).hexdigest()