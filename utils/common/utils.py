import logging
logger = logging.getLogger(__name__)
from django.conf import settings


# MAIN URL ------------------------------------------------------------------
MAIN_URL = 'http://localhost:3000'


# FILE DIRECTION Handler ------------------------------------------
import os
from uuid import uuid4
import datetime

class FileUpload:
    def __init__(self, app_name, direction, folder):
        self.app_name = app_name
        self.direction = direction
        self.folder = folder

    def dir_upload(self, instanse, filename):
        prefix, suffix = os.path.splitext(filename)
        unique_filename = f'{uuid4()}{suffix}'
        today = datetime.datetime.now().strftime("%Y/%m/%d")
        return f'{self.app_name}/{self.direction}/{self.folder}/{today}/{unique_filename}'

    def to_dict(self):
        return {
            "app_name": self.app_name,
            "direction": self.direction,
            "folder": self.folder,
        }

    def deconstruct(self):
        return (
            'utils.FileUpload',
            [self.app_name, self.direction, self.folder],
            {}
        )


# FILE DIRECTION Handler For Converted Files --------------------------
import tempfile
from django.core.files.storage import default_storage
from storages.backends.s3boto3 import S3Boto3Storage
def get_converted_path(instance, original_path: str, fileupload, extension: str) -> tuple[str, str]:
    today = datetime.datetime.now().strftime("%Y/%m/%d")
    unique_filename = f'{uuid4()}{extension}'
    relative_path = f'{fileupload.app_name}/{fileupload.direction}/{fileupload.folder}/{today}/{unique_filename}'

    # اگر storage روی S3 بود، فایل را در مسیر موقتی بسازیم
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
def send_sms(phone_number, message):
    try:
        # Initialize the SNS client
        sns_client = boto3.client(
            'sns',
            region_name=settings.AWS_SNS_REGION,
            aws_access_key_id=settings.AWS_SNS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SNS_SECRET_ACCESS_KEY,
        )

        # Send SMS
        response = sns_client.publish(
            PhoneNumber=phone_number,
            Message=message,
        )
        return {"success": True, "message_id": response['MessageId']}
    except (BotoCoreError, ClientError) as e:
        return {"success": False, "error": str(e)}


# CREATE TOKEN --------------------------------------------------------------
import secrets
def generate_reset_token(length=30):
    token = secrets.token_urlsafe(length)
    return token


# Slug Mixin -----------------------------------------------------------------
from django.db import models, IntegrityError, transaction
from django.utils.text import slugify
from django.urls import reverse

class SlugMixin(models.Model):
    """
    Mixin to generate a unique, URL-friendly slug once per object.
    Keeps the slug stable on updates (unless manually changed).
    """
    slug = models.SlugField(
        max_length=140, unique=True, blank=True, null=True, db_index=True, verbose_name="Slug"
    )

    # Tuning knobs
    SLUG_MAX_LEN = 140
    SLUG_RETRY_LIMIT = 5  # safety net for rare race conditions

    class Meta:
        abstract = True

    def get_slug_source(self) -> str:
        """Child classes must return a human-readable string used to build the slug."""
        raise NotImplementedError("Subclasses should implement this!")

    def _build_base_slug(self) -> str:
        """Build base slug (truncated to max length) with a safe fallback."""
        base = slugify(self.get_slug_source() or "") or "item"
        return base[: self.SLUG_MAX_LEN]

    def _dedupe_slug(self, base: str) -> str:
        """
        Ensure uniqueness by appending -1, -2, ... if needed.
        Excludes current instance (important on updates).
        """
        Model = self.__class__
        candidate = base
        i = 1
        while Model.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            suffix = f"-{i}"
            candidate = f"{base[: self.SLUG_MAX_LEN - len(suffix)]}{suffix}"
            i += 1
        return candidate

    def save(self, *args, **kwargs):
        """
        Generate slug once if missing.
        Use a small retry loop to handle DB-level unique collisions under race.
        """
        if not self.slug:
            base = self._build_base_slug()
            self.slug = self._dedupe_slug(base)

        retries = 0
        while True:
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as e:
                # Retry only if it's likely the slug unique constraint
                if retries < self.SLUG_RETRY_LIMIT and "slug" in str(e).lower():
                    retries += 1
                    # Rebuild a new unique candidate and try again
                    base = (self.slug.rsplit("-", 1)[0]
                            if "-" in (self.slug or "")
                            else self._build_base_slug())
                    self.slug = self._dedupe_slug(base)
                    continue
                raise

    def get_absolute_url(self):
        """Reverse using slug if available; fallback to pk."""
        if not hasattr(self, "url_name"):
            raise NotImplementedError("Subclasses must define 'url_name' for reverse().")
        if self.slug:
            return reverse(self.url_name, kwargs={"slug": self.slug})
        return reverse(self.url_name, kwargs={"pk": self.pk})

 