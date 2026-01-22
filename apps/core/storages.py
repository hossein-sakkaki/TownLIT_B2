# apps/core/storages.py
from storages.backends.s3boto3 import S3Boto3Storage

# Default private storage (everything except email)
class PrivateMediaStorage(S3Boto3Storage):
    location = "private"
    default_acl = "private"
    querystring_auth = True


# Public storage ONLY for email images
class PublicEmailStorage(S3Boto3Storage):
    location = "public/emails"
    default_acl = "public-read"
    querystring_auth = False
