# common/views/media_proxy.py

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from urllib.parse import unquote, quote
import logging
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from common.aws.s3_utils import generate_presigned_url

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def serve_s3_media_file(request):
    key = request.query_params.get('key')
    force_download = request.query_params.get('download') == '1'

    if not key:
        return HttpResponseBadRequest("Missing 'key' query parameter.")

    key = unquote(key.strip())

    is_hls_manifest = key.endswith(".m3u8")
    is_hls_segment = key.endswith(".ts")

    if is_hls_manifest or is_hls_segment:
        logger.info(f"⏳ Streaming HLS asset from S3: {key}")
        try:
            s3 = boto3.client(
                's3',
                region_name=settings.AWS_S3_REGION_NAME,
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
            )
            s3_response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)

            # 📌 اگر manifest است (متنی)، باید decode کنیم
            if is_hls_manifest:
                raw_content = s3_response['Body'].read().decode("utf-8")
                content_type = "application/vnd.apple.mpegurl"

                # 🔁 اصلاح مسیرها
                base_path = "/".join(key.split("/")[:-1])
                proxy_base = request.build_absolute_uri('/media-proxy/')

                def fix_line(line):
                    line = line.strip()
                    if line.endswith(".m3u8") or line.endswith(".ts"):
                        relative_path = f"{base_path}/{line}"
                        return f"{proxy_base}?key={quote(relative_path)}"
                    return line

                fixed_content = "\n".join([fix_line(line) for line in raw_content.splitlines()])
                return HttpResponse(fixed_content, content_type=content_type)

            else:
                # 🎯 فایل segment یا دیگر فایل binary
                content_type = "video/MP2T"
                return HttpResponse(s3_response['Body'].read(), content_type=content_type)

        except ClientError as e:
            logger.error(f"S3 access error for HLS file: {key} | Error: {e}")
            return HttpResponseBadRequest("Unable to stream HLS file.")

    # سایر فایل‌ها با ریدایرکت
    try:
        signed_url = generate_presigned_url(key, force_download=force_download)
        if not signed_url:
            logger.warning(f"Failed to generate presigned URL for: {key}")
            return HttpResponseBadRequest("Unable to access requested file.")

        logger.info(f"Redirecting to presigned URL: {key}")
        return HttpResponseRedirect(signed_url)

    except Exception as e:
        logger.error(f"Unexpected error in media proxy: {e}")
        return HttpResponseBadRequest("Error serving requested file.")
