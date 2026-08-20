# utils/email/core/ses_sender.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


import logging

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import boto3

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
)

from django.conf import settings

from .attachments import (
    build_attachment,
)


logger = logging.getLogger(__name__)


def send_email(
    subject,
    message,
    html_content,
    to,
):
    """
    Send standard SES email.
    """

    recipients = _normalize_recipients(
        to
    )

    if not recipients:
        return False

    try:
        client = _ses_client()

        response = client.send_email(
            Source=_sender(),
            Destination={
                "ToAddresses": recipients,
            },
            Message={
                "Subject": {
                    "Data": subject,
                    "Charset": "UTF-8",
                },
                "Body": {
                    "Text": {
                        "Data": message or "",
                        "Charset": "UTF-8",
                    },
                    "Html": {
                        "Data": html_content or "",
                        "Charset": "UTF-8",
                    },
                },
            },
            ReturnPath=_return_path(),
        )

        logger.info(
            "SES email sent msg_id=%s",
            response.get(
                "MessageId"
            ),
        )

        return True

    except (
        BotoCoreError,
        ClientError,
    ) as error:

        logger.error(
            "SES email failed: %s",
            error,
            exc_info=True,
        )

        return False


def send_email_with_attachments(
    subject,
    message,
    html_content,
    to,
    attachments=None,
):
    """
    Send SES email with attachments.
    """

    recipients = _normalize_recipients(
        to
    )

    attachments = attachments or []

    if not recipients:
        return False

    try:
        client = _ses_client()

        raw_message = _build_raw_message(
            subject=subject,
            message=message,
            html_content=html_content,
            recipients=recipients,
            attachments=attachments,
        )

        response = client.send_raw_email(
            Source=_sender(),
            Destinations=recipients,
            RawMessage={
                "Data": raw_message.as_string(),
            },
        )

        logger.info(
            "SES raw email sent msg_id=%s",
            response.get(
                "MessageId"
            ),
        )

        return True

    except (
        BotoCoreError,
        ClientError,
    ) as error:

        logger.error(
            "SES raw email failed: %s",
            error,
            exc_info=True,
        )

        return False


def _build_raw_message(
    *,
    subject,
    message,
    html_content,
    recipients,
    attachments,
):
    """
    Build MIME raw email.
    """

    raw = MIMEMultipart(
        "mixed"
    )

    raw["Subject"] = subject
    raw["From"] = _sender()
    raw["To"] = ", ".join(
        recipients
    )
    raw["Return-Path"] = _return_path()

    body = MIMEMultipart(
        "alternative"
    )

    body.attach(
        MIMEText(
            message or "",
            "plain",
            "utf-8",
        )
    )

    body.attach(
        MIMEText(
            html_content or "",
            "html",
            "utf-8",
        )
    )

    raw.attach(body)

    for item in attachments:
        raw.attach(
            build_attachment(
                item
            )
        )

    return raw


def _ses_client():
    """
    Create SES client.
    """

    return boto3.client(
        "ses",
        region_name=settings.AWS_SES_REGION_NAME,
        aws_access_key_id=(
            settings.AWS_SES_ACCESS_KEY_ID
        ),
        aws_secret_access_key=(
            settings.AWS_SES_SECRET_ACCESS_KEY
        ),
    )


def _sender():
    return settings.AWS_SES_EMAIL_FROM


def _return_path():
    return getattr(
        settings,
        "AWS_SES_RETURN_PATH",
        _sender(),
    )


def _normalize_recipients(
    to,
):
    if isinstance(to, str):
        return [
            to
        ]

    return list(to or [])