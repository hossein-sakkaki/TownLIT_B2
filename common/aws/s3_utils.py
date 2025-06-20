# common/s3_utils.py
import boto3
from django.conf import settings
from botocore.exceptions import ClientError
import logging


def get_file_size(key: str) -> int:
    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    response = s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    return response['ContentLength']  # bytes


def generate_presigned_url(key: str, expires_in: int = None, force_download: bool = False) -> str:
    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )

    if expires_in is None:
        try:
            size_bytes = get_file_size(key)
            size_mb = size_bytes / (1024 * 1024)
            # Use 6 seconds per MB, clamp between 300 and 3600 seconds
            expires_in = min(max(int(size_mb * 6), 300), 3600)
        except Exception as e:
            logging.warning(f"Could not get file size for dynamic expiration: {e}")
            expires_in = 600  # Fallback default

    params = {'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': key}

    if force_download:
        filename = key.split("/")[-1]
        params['ResponseContentDisposition'] = f'attachment; filename="{filename}"'

    try:
        return s3.generate_presigned_url('get_object', Params=params, ExpiresIn=expires_in)
    except ClientError as e:
        logging.error(f"Error generating signed URL: {e}")
        return None


def get_file_url(key: str, default_url: str = None, expires_in: int = None, force_download: bool = False) -> str:
    if not key:
        return default_url

    if key.startswith("http://") or key.startswith("https://"):
        return key

    if getattr(settings, 'SERVE_FILES_PUBLICLY', False):
        return f"{settings.MEDIA_URL}{key}"

    try:
        return generate_presigned_url(key, expires_in=expires_in, force_download=force_download)
    except Exception as e:
        logging.error(f"get_file_url fallback due to error: {e}")
        return default_url
