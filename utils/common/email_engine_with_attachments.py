# apps/common/email_engine_with_attachments.py

from django.conf import settings
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import logging

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email_with_attachments(subject, message, html_content, to, attachments=None):
    """
    Send SES email with optional attachments.

    attachments format:
    [
        {
            "filename": "pay_stub.pdf",
            "content": b"...",
            "mime_type": "application/pdf",
        }
    ]
    """

    attachments = attachments or []

    if isinstance(to, str):
        to = [to]

    ses_client = boto3.client(
        "ses",
        region_name=getattr(settings, "AWS_SES_REGION_NAME", None),
        aws_access_key_id=getattr(settings, "AWS_SES_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SES_SECRET_ACCESS_KEY", None),
    )

    sender = getattr(settings, "AWS_SES_EMAIL_FROM", "")
    return_path = getattr(settings, "AWS_SES_RETURN_PATH", sender)

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(to)
        msg["Return-Path"] = return_path

        body = MIMEMultipart("alternative")
        body.attach(MIMEText(message or "", "plain", "utf-8"))
        body.attach(MIMEText(html_content or "", "html", "utf-8"))
        msg.attach(body)

        for item in attachments:
            filename = item["filename"]
            content = item["content"]
            mime_type = item.get("mime_type", "application/octet-stream")

            main_type, sub_type = mime_type.split("/", 1)

            part = MIMEApplication(content, _subtype=sub_type)
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(part)

        response = ses_client.send_raw_email(
            Source=sender,
            Destinations=to,
            RawMessage={"Data": msg.as_string()},
        )

        logger.info(
            "SES sent raw email: msg_id=%s to=%s",
            response.get("MessageId"),
            to,
        )
        return True

    except (BotoCoreError, ClientError) as error:
        logger.error("SES send_raw_email error to=%s: %s", to, error, exc_info=True)
        return False
    except Exception as error:
        logger.error("Email attachment send failed to=%s: %s", to, error, exc_info=True)
        return False