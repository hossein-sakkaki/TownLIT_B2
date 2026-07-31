# utils/common/utils.py

import logging
from django.utils.deconstruct import deconstructible
logger = logging.getLogger(__name__)
from django.conf import settings
import os
from uuid import uuid4
import datetime

# FILE DIRECTION Handler ------------------------------------------
@deconstructible
class FileUpload:
    def __init__(self, app_name, direction, folder):
        self.app_name = app_name
        self.direction = direction
        self.folder = folder

    def __call__(self, instance, filename):
        # Allow using the object itself as upload_to.
        return self.dir_upload(instance, filename)

    def dir_upload(self, instance, filename):
        # Keep the exact same path-building behavior.
        _, suffix = os.path.splitext(filename)
        unique_filename = f"{uuid4()}{suffix}"
        today = datetime.datetime.now().strftime("%Y/%m/%d")
        return f"{self.app_name}/{self.direction}/{self.folder}/{today}/{unique_filename}"

    def to_dict(self):
        return {
            "app_name": self.app_name,
            "direction": self.direction,
            "folder": self.folder,
        }

    def deconstruct(self):
        # Keep a correct import path for migrations.
        return (
            "utils.common.utils.FileUpload",
            [self.app_name, self.direction, self.folder],
            {},
        )


# FILE DIRECTION Handler For Converted Files --------------------------
import tempfile
from django.core.files.storage import default_storage
from storages.backends.s3boto3 import S3Boto3Storage
def get_converted_path(instance, original_path: str, fileupload, extension: str) -> tuple[str, str]:
    today = datetime.datetime.now().strftime("%Y/%m/%d")
    unique_filename = f'{uuid4()}{extension}'
    relative_path = f'{fileupload.app_name}/{fileupload.direction}/{fileupload.folder}/{today}/{unique_filename}'

    if isinstance(default_storage, S3Boto3Storage):
        absolute_path = os.path.join(tempfile.gettempdir(), unique_filename)
    else:
        absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)

    return absolute_path, relative_path


# HLS OUTPUT DIRECTION Handler For Converted Files --------------------
def get_hls_output_dir(instance, fileupload: FileUpload) -> tuple[str, str]:
    today = datetime.datetime.now().strftime("%Y/%m/%d")
    unique_folder = str(uuid4())
    relative_dir = f"{fileupload.app_name}/{fileupload.direction}/{fileupload.folder}/{today}/{unique_folder}"

    if isinstance(default_storage, S3Boto3Storage):
        absolute_dir = os.path.join(tempfile.gettempdir(), unique_folder)
    else:
        absolute_dir = os.path.join(settings.MEDIA_ROOT, relative_dir)

    return absolute_dir, relative_dir


# CREATE RANDOM Code ---------------------------------------------------
def create_active_code(count):
    import random
    count-=1
    return random.randint(10**count, 10**(count+1)-1)
        
# utils/common/utils.py     
# SEND ACTIVE CODE by AWS EMAIL ------------------------------------------
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import logging

logger = logging.getLogger(__name__)

def send_email(subject, message, html_content, to):
    ses_client = boto3.client(
        'ses',
        region_name=getattr(settings, "AWS_SES_REGION_NAME", None),
        aws_access_key_id=getattr(settings, "AWS_SES_ACCESS_KEY_ID", None),
        aws_secret_access_key=getattr(settings, "AWS_SES_SECRET_ACCESS_KEY", None),
    )
    if isinstance(to, str):
        to = [to]

    try:
        response = ses_client.send_email(
            Source=getattr(settings, "AWS_SES_EMAIL_FROM", ""),
            Destination={'ToAddresses': to},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': message, 'Charset': 'UTF-8'},
                    'Html': {'Data': html_content, 'Charset': 'UTF-8'},
                },
            },
            ReturnPath=getattr(settings, "AWS_SES_RETURN_PATH", getattr(settings, "AWS_SES_EMAIL_FROM", "")),
        )
        logger.info("SES sent email: msg_id=%s to=%s", response.get("MessageId"), to)
        return True
    except (BotoCoreError, ClientError) as error:
        logger.error("SES send_email error to=%s: %s", to, error, exc_info=True)
        return False
    

# SEND ACTIVE CODE by AWS SMS ------------------------------------------
# utils/sms.py

import logging
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger("townlit.sms")


def mask_phone(phone: str) -> str:
    if not phone:
        return ""
    if len(phone) <= 6:
        return "***"
    return f"{phone[:3]}***{phone[-4:]}"


def send_sms(phone_number, message):
    logger.info(
        "SMS_SEND_ATTEMPT phone=%s region=%s message_len=%s",
        mask_phone(phone_number),
        settings.AWS_SNS_REGION,
        len(message or ""),
    )

    try:
        sns_client = boto3.client(
            "sns",
            region_name=settings.AWS_SNS_REGION,
            aws_access_key_id=settings.AWS_SNS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SNS_SECRET_ACCESS_KEY,
        )

        response = sns_client.publish(
            PhoneNumber=phone_number,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {
                    "DataType": "String",
                    "StringValue": "Transactional",
                }
            },
        )

        message_id = response.get("MessageId")
        request_id = response.get("ResponseMetadata", {}).get("RequestId")

        logger.info(
            "SMS_SEND_ACCEPTED phone=%s message_id=%s aws_request_id=%s http_status=%s",
            mask_phone(phone_number),
            message_id,
            request_id,
            response.get("ResponseMetadata", {}).get("HTTPStatusCode"),
        )

        return {
            "success": True,
            "message_id": message_id,
            "aws_request_id": request_id,
        }

    except ClientError as e:
        error = e.response.get("Error", {})
        logger.exception(
            "SMS_SEND_CLIENT_ERROR phone=%s code=%s message=%s",
            mask_phone(phone_number),
            error.get("Code"),
            error.get("Message"),
        )
        return {
            "success": False,
            "error": str(e),
            "aws_error_code": error.get("Code"),
            "aws_error_message": error.get("Message"),
        }

    except BotoCoreError as e:
        logger.exception(
            "SMS_SEND_BOTOCORE_ERROR phone=%s error=%s",
            mask_phone(phone_number),
            str(e),
        )
        return {"success": False, "error": str(e)}

    except Exception as e:
        logger.exception(
            "SMS_SEND_UNKNOWN_ERROR phone=%s error=%s",
            mask_phone(phone_number),
            str(e),
        )
        return {"success": False, "error": str(e)}


# CREATE TOKEN --------------------------------------------------------------
import secrets
def generate_reset_token(length=30):
    token = secrets.token_urlsafe(length)
    return token

