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


def get_file_url(key: str, expires_in: int = 600) -> str:
    """
    Return public URL or presigned URL based on settings.
    """
    if not key:
        return None

    # حالت public
    if getattr(settings, 'SERVE_FILES_PUBLICLY', False):
        return f"{settings.MEDIA_URL}{key}"

    # حالت private
    return generate_presigned_url(key, expires_in)
