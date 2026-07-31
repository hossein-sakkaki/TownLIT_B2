# apps/journey_insights/tasks.py

from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.journey_insights.services.monthly_reports import (
    generate_monthly_insight_report,
)


CustomUser = get_user_model()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def generate_user_monthly_insight(
    self,
    *,
    user_id: int,
    year: int,
    month: int,
):
    report = generate_monthly_insight_report(
        user=CustomUser.objects.get(pk=user_id),
        year=year,
        month=month,
    )

    return {
        "report_id": report.pk,
        "public_id": str(report.public_id),
        "status": report.status,
    }


@shared_task
def generate_monthly_insights_batch(
    *,
    year: int,
    month: int,
):
    user_ids = (
        CustomUser.objects
        .filter(
            is_active=True,
            is_deleted=False,
            is_member=True,
        )
        .values_list("id", flat=True)
        .iterator(chunk_size=500)
    )

    queued = 0

    for user_id in user_ids:
        generate_user_monthly_insight.delay(
            user_id=user_id,
            year=year,
            month=month,
        )

        queued += 1

    return {
        "year": year,
        "month": month,
        "queued": queued,
    }