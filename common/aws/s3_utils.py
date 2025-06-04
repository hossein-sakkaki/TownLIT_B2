# common/aws/s3_utils.py
import boto3
from django.conf import settings


def generate_presigned_url(key: str, expires_in: int = 600) -> str:
    """
    Generate a presigned URL for private S3 object.
    """
    s3 = boto3.client(
        's3',
        region_name=settings.AWS_S3_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )
    return s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': key,
        },
        ExpiresIn=expires_in
    )


def get_file_url(key: str, default_url: str = None, expires_in: int = 600) -> str:
    if not key:
        return default_url

    if key.startswith("http://") or key.startswith("https://"):
        return key

    if getattr(settings, 'SERVE_FILES_PUBLICLY', False):
        public_url = f"{settings.MEDIA_URL}{key}"
        return public_url

    try:
        url = generate_presigned_url(key, expires_in)
        return url
    except Exception as e:
        return default_url
