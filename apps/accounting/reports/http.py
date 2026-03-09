# apps/accounting/reports/http.py

from django.http import HttpResponse


CONTENT_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def build_file_response(*, content: bytes, filename: str, file_format: str) -> HttpResponse:
    """
    Build downloadable file response.
    """

    response = HttpResponse(
        content,
        content_type=CONTENT_TYPES[file_format],
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response