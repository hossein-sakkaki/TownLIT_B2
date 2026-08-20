# utils/email/core/attachments.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-19.
# Last Update by Hossein Sakkaki on 2026-08-19.


from email.mime.application import MIMEApplication


def build_attachment(
    attachment: dict,
) -> MIMEApplication:
    """
    Build MIME attachment part.
    """

    filename = attachment["filename"]
    content = attachment["content"]

    mime_type = attachment.get(
        "mime_type",
        "application/octet-stream",
    )

    subtype = _resolve_subtype(
        mime_type
    )

    part = MIMEApplication(
        content,
        _subtype=subtype,
    )

    part.add_header(
        "Content-Disposition",
        "attachment",
        filename=filename,
    )

    return part


def _resolve_subtype(
    mime_type: str,
) -> str:
    """
    Resolve MIME subtype.
    """

    if "/" not in mime_type:
        return "octet-stream"

    _, subtype = mime_type.split(
        "/",
        1,
    )

    return subtype or "octet-stream"