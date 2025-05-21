import fitz
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type
import mimetypes

def validate_pdf_file(value):
    mime_type, _ = mimetypes.guess_type(value.name)
    file_type = validate_file_type(value.name, mime_type)
    if file_type != "file":
        raise ValidationError("Only PDF files are allowed.")
    if value.size > 10 * 1024 * 1024:
        raise ValidationError("PDF exceeds the 10MB limit.")
    try:
        pdf = fitz.open(stream=value.read(), filetype="pdf")
    except Exception as e:
        raise ValidationError(f"Invalid PDF file: {str(e)}")
    if pdf.page_count == 0:
        raise ValidationError("PDF is empty.")
    if pdf.is_encrypted:
        raise ValidationError("Encrypted PDFs are not allowed.")
    if pdf.pdf_version < '1.4':
        raise ValidationError("Minimum supported PDF version is 1.4.")
