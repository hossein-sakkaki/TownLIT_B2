import fitz
import mimetypes
from django.core.exceptions import ValidationError
from validators.mime_type_validator import validate_file_type

MIN_PDF_VERSION = 1.4
MAX_SIZE_MB = 10

def _reset(fp):
    try:
        fp.seek(0)
    except Exception:
        pass

def validate_pdf_file(value):
    # 1) quick MIME / name gate
    mime_type, _ = mimetypes.guess_type(getattr(value, "name", None))
    file_type = validate_file_type(getattr(value, "name", ""), mime_type)
    if file_type != "file":
        raise ValidationError("Only PDF files are allowed.")
    if value.size and value.size > MAX_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"PDF exceeds the {MAX_SIZE_MB}MB limit.")

    # 2) read small header to verify signature and version
    _reset(value)
    head = value.read(16) or b""
    if not head.startswith(b"%PDF-"):
        raise ValidationError("Invalid PDF signature.")
    # parse version from header: e.g. %PDF-1.7
    ver = None
    try:
        # take bytes after '%PDF-' up to next non-digit/non-dot
        vs = head[5:10].decode("ascii", errors="ignore")
        # typical forms: '1.3', '1.4', '1.7'
        ver = float(vs.split()[0][:3])
    except Exception:
        # if parsing fails, treat as too old / invalid
        raise ValidationError("Unrecognized PDF version.")

    if ver < MIN_PDF_VERSION:
        raise ValidationError(f"Minimum supported PDF version is {MIN_PDF_VERSION:g}.")

    # 3) deep check with PyMuPDF
    _reset(value)
    try:
        # read full stream for fitz open (needs bytes)
        data = value.read()
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ValidationError(f"Invalid PDF file: {str(e)}")

    try:
        if getattr(doc, "page_count", 0) == 0:
            raise ValidationError("PDF is empty.")
        # encryption flag varies across versions
        if getattr(doc, "is_encrypted", False) or getattr(doc, "needs_pass", False):
            raise ValidationError("Encrypted PDFs are not allowed.")
    finally:
        try:
            doc.close()
        except Exception:
            pass

    # 4) ensure the uploaded file pointer is rewound for Django storage
    _reset(value)
