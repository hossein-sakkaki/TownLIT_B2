# apps/communication/services/external_campaigns.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from datetime import datetime
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.utils import timezone

from apps.communication.constants import LAYOUT_BASE_SITE
from apps.communication.models import ExternalContact
from utils.common.file_reader import read_csv_or_json
from utils.email.email_tools import send_custom_email
from utils.email.token_generator import generate_external_email_token
from .links import CommunicationURLBuilder

logger = logging.getLogger(__name__)

CustomUser = get_user_model()


def send_external_email_campaign(campaign):
    """
    Send one legacy file-driven external campaign.
    """

    rows = _read_campaign_rows(
        campaign
    )

    if not rows:
        return {
            "sent": 0,
            "skipped_duplicates": 0,
            "failed_saves": 0,
        }

    registered_emails = {
        email.strip().lower()
        for email in CustomUser.objects.exclude(
            email=""
        ).values_list(
            "email",
            flat=True,
        )
        if email
    }

    existing_emails = {
        email.strip().lower()
        for email in ExternalContact.objects.values_list(
            "email",
            flat=True,
        )
        if email
    }

    seen_emails = set()
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for row in rows:
        email = (
            row.get("email", "")
            or ""
        ).strip().lower()

        if (
            not email
            or email in seen_emails
            or email in existing_emails
            or email in registered_emails
        ):
            skipped_count += 1
            continue

        seen_emails.add(email)

        contact = _create_external_contact(
            campaign=campaign,
            row=row,
            email=email,
        )

        if not contact:
            failed_count += 1
            continue

        if contact.is_unsubscribed or contact.became_user:
            skipped_count += 1
            continue

        context = _build_context(
            email=email,
            row=row,
        )

        body = Template(
            campaign.html_body or ""
        ).render(
            Context(context)
        )

        subject = Template(
            campaign.subject or ""
        ).render(
            Context(context)
        )

        context["content"] = body

        layout = (
            campaign.template.layout
            if campaign.template_id
            else LAYOUT_BASE_SITE
        )

        success = send_custom_email(
            to=email,
            subject=subject,
            template_path=f"{layout}.html",
            context=context,
        )

        if success:
            sent_count += 1

            ExternalContact.objects.filter(
                pk=contact.pk
            ).update(
                last_contacted_at=timezone.now()
            )
        else:
            logger.error(
                "Legacy external email failed email=%s campaign=%s",
                email,
                campaign.id,
            )

    campaign.is_sent = True
    campaign.sent_at = timezone.now()
    campaign.save(
        update_fields=[
            "is_sent",
            "sent_at",
        ]
    )

    return {
        "sent": sent_count,
        "skipped_duplicates": skipped_count,
        "failed_saves": failed_count,
    }


def _read_campaign_rows(campaign):
    try:
        with campaign.csv_file.open("rb") as file_obj:
            return read_csv_or_json(
                file_obj
            ) or []

    except Exception as error:
        raise ValueError(
            f"Unable to read external campaign file: {error}"
        ) from error


def _create_external_contact(
    *,
    campaign,
    row,
    email,
):
    try:
        return ExternalContact.objects.create(
            email=email,
            name=_clean(row.get("name")),
            family=_clean(row.get("family")),
            gender=_clean(row.get("gender")),
            birth_date=_parse_date(
                row.get("birth_date"),
                "%Y-%m-%d",
            ),
            nation=_clean(row.get("nation")),
            country=_clean(row.get("country")),
            phone=_clean(row.get("phone")),
            recognize=_clean(row.get("recognize")),
            registre_date=_parse_registration_date(
                row.get("registre_date")
            ),
            source_campaign=campaign,
            source="legacy_import",
        )

    except Exception as error:
        logger.exception(
            "Unable to save external contact email=%s error=%s",
            email,
            error,
        )
        return None


def _build_context(*, email, row):
    token = generate_external_email_token(
        email
    )

    return {
        "email": email,
        "first_name": _clean(row.get("name")) or "Friend",
        "username": _clean(row.get("name")) or "guest_user",
        "site_domain": settings.SITE_URL,
        "logo_base_url": settings.EMAIL_LOGO_URL,
        "current_year": timezone.now().year,
        "unsubscribe_url": (
            CommunicationURLBuilder()
            .external_unsubscribe(token)
        ),
    }


def _parse_registration_date(value):
    return (
        _parse_date(
            value,
            "%Y-%m-%d %H:%M:%S.%f",
        )
        or _parse_date(
            value,
            "%Y-%m-%d %H:%M:%S",
        )
    )


def _parse_date(value, date_format):
    value = _clean(value)

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            date_format,
        )
    except (TypeError, ValueError):
        return None


def _clean(value):
    return str(value or "").strip()