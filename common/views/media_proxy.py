from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from rest_framework.decorators import permission_classes
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from urllib.parse import unquote, quote
import logging
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from common.aws.aws_clients import s3_client
from common.aws.s3_utils import generate_presigned_url

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "HEAD", "OPTIONS"])
@permission_classes([AllowAny])
def serve_s3_media_file(request):
    key = request.GET.get('key')
    force_download = request.GET.get('download') == '1'

    if not key:
        return HttpResponseBadRequest("Missing 'key' query parameter.")

    key = unquote(key.strip())

    is_hls_manifest = key.endswith(".m3u8")
    is_hls_segment = key.endswith(".ts")



    def add_cors_headers(response):
        if settings.CORS_ALLOW_ALL_ORIGINS:
            response["Access-Control-Allow-Origin"] = "*"
        else:
            allowed_origins = getattr(settings, "CORS_ALLOWED_ORIGINS", [])
            request_origin = request.headers.get("Origin")
            if request_origin in allowed_origins:
                response["Access-Control-Allow-Origin"] = request_origin
        response["Access-Control-Allow-Methods"] = "GET, HEAD, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Range, Content-Type"
        response["Access-Control-Expose-Headers"] = "Content-Length, Content-Range"
        response["Access-Control-Allow-Credentials"] = "true"
        return response


    if is_hls_manifest or is_hls_segment:
        logger.info(f"⏳ Streaming HLS asset from S3: {key}")
        try:
            s3 = s3_client
            s3_response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)

            if request.method == "HEAD":
                response = HttpResponse()
                content_type = "application/vnd.apple.mpegurl" if is_hls_manifest else "video/MP2T"
                response["Content-Type"] = content_type
                if "ContentLength" in s3_response:
                    response["Content-Length"] = str(s3_response["ContentLength"])
                return add_cors_headers(response)
            
            if request.method == "OPTIONS":
                response = HttpResponse()
                return add_cors_headers(response)

            if is_hls_manifest:
                raw_content = s3_response['Body'].read().decode("utf-8")
                content_type = "application/x-mpegURL"


                base_path = "/".join(key.split("/")[:-1])
                # proxy_base = request.build_absolute_uri('/media-proxy/')
                proxy_base = "/media-proxy/"

                def fix_line(line):
                    line = line.strip()
                    if line.endswith(".m3u8") or line.endswith(".ts"):
                        relative_path = f"{base_path}/{line}"
                        return f"{proxy_base}?key={quote(relative_path)}"
                    return line

                fixed_content = "\n".join([fix_line(line) for line in raw_content.splitlines()])
                response = HttpResponse(fixed_content, content_type=content_type)
                return add_cors_headers(response)

            else:
                content_type = "video/MP2T"
                response = HttpResponse(s3_response['Body'].read(), content_type=content_type)
                return add_cors_headers(response)

        except ClientError as e:
            logger.error(f"S3 access error for HLS file: {key} | Error: {e}")
            return HttpResponseBadRequest("Unable to stream HLS file.")

    try:
        signed_url = generate_presigned_url(key, force_download=force_download)
        if not signed_url:
            logger.warning(f"Failed to generate presigned URL for: {key}")
            return HttpResponseBadRequest("Unable to access requested file.")

        logger.info(f"Redirecting to presigned URL: {key}")
        response = HttpResponseRedirect(signed_url)
        return add_cors_headers(response)

    except Exception as e:
        logger.error(f"Unexpected error in media proxy: {e}")
        return HttpResponseBadRequest("Error serving requested file.")
