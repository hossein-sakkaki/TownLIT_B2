import logging
logger = logging.getLogger(__name__)


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


# FILE DIRECTION Handler For Converted Files --------------------
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


# CREATE RANDOM Code ------------------------------------------
def create_active_code(count):
    import random
    count-=1
    return random.randint(10**count, 10**(count+1)-1)
        
        
# SEND ACTIVE CODE by AWS EMAIL ------------------------------------------
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

def send_email(subject, message, html_content, to):
    # Initialize the SES client
    ses_client = boto3.client(
        'ses',
        region_name=settings.AWS_SES_REGION_NAME,
        aws_access_key_id=settings.AWS_SES_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SES_SECRET_ACCESS_KEY,
    )

    if isinstance(to, str):
        to = [to]

    # Prepare the email parameters
    try:
        response = ses_client.send_email(
            Source=settings.AWS_SES_EMAIL_FROM,  # Verified email address
            Destination={
                'ToAddresses': to,
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8',
                },
                'Body': {
                    'Text': {
                        'Data': message,
                        'Charset': 'UTF-8',
                    },
                    'Html': {
                        'Data': html_content,
                        'Charset': 'UTF-8',
                    },
                },
            },
            ReturnPath=settings.AWS_SES_RETURN_PATH,
        )
        print(f"Email sent successfully: {response['MessageId']}")
        return True
    except (BotoCoreError, ClientError) as error:
        print(f"An error occurred while sending the email: {error}")
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


# Push Notification ---------------------------------------------------------
from pyfcm import FCMNotification
def send_push_notification(registration_id, message_title, message_body):
    push_service = FCMNotification(api_key=settings.FCM_API_KEY)
    result = push_service.notify_single_device(
        registration_id=registration_id,
        message_title=message_title,
        message_body=message_body
    )
    return result

# Slug Mixin -----------------------------------------------------------------
from django.utils.text import slugify
from django.db import models
from django.urls import reverse
class SlugMixin(models.Model):
    slug = models.SlugField(unique=True, blank=True, null=True, verbose_name='Slug')

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.get_slug_source())
            slug = base_slug
            n = 1
            while self.__class__.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_slug_source(self):
        raise NotImplementedError("Subclasses should implement this!")

    def get_absolute_url(self):
        if hasattr(self, 'url_name'):
            return reverse(self.url_name, kwargs={"slug": self.get_slug_source()})
        raise NotImplementedError("Subclasses must define 'url_name' property for reverse URL.")

    class Meta:
        abstract = True
        

# Identity Verification Engine --------------------------------------------------
import requests
from django.conf import settings

VERIFF_API_KEY = settings.VERIFF_API_KEY
VERIFF_API_URL = 'https://api.veriff.me/v1/sessions'

def create_veriff_session(member):
    user = member.name
    headers = {
        'Authorization': f'Bearer {VERIFF_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "verification": {
            "person": {
                "firstName": user.name,
                "lastName": user.family
            },
            "document": {
                "number": member.identity_document.name if member.identity_document else None
            },
            "lang": "en",
            "timestamp": True,
        }
    }
    try:
        response = requests.post(VERIFF_API_URL, json=data, headers=headers)
        response_data = response.json()
        if response.status_code == 201:
            return response_data
        else:
            logging.error(f"Failed to create Veriff session: {response_data}")
            raise Exception(f"Error creating Veriff session: {response_data.get('error')}")
    except requests.RequestException as e:
        logging.error(f"Request to Veriff API failed: {str(e)}")
        raise Exception(f"Request to Veriff API failed: {str(e)}")


# Get Verify Status -------------------------------------------------------------
VERIFF_BASE_URL = "https://stationapi.veriff.com/v1"

def get_veriff_status(session_id):
    url = f"{VERIFF_BASE_URL}/sessions/{session_id}"
    headers = {
        "Authorization": f"Bearer {settings.VERIFF_API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            return response_data.get('status', 'unknown')
        else:
            logging.error(f"Failed to fetch Veriff session status: {response_data}")
            raise Exception(f"Failed to fetch Veriff session status: {response_data.get('error')}")
    except requests.RequestException as e:
        logging.error(f"Request to Veriff API failed: {str(e)}")
        raise Exception(f"Request to Veriff API failed: {str(e)}")
