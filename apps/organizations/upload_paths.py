# apps/organizations/upload_paths.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-30.
# Last Update by Hossein Sakkaki on 2026-08-30.
#

from utils.common.utils import FileUpload


ORGANIZATION_LOGO_UPLOAD = FileUpload(
    "organizations",
    "logos",
    "organization",
)

ORGANIZATION_VERIFICATION_UPLOAD = FileUpload(
    "organizations",
    "verification",
    "organization_verification",
)


def organization_logo_upload_to(instance, filename):
    return ORGANIZATION_LOGO_UPLOAD.dir_upload(instance, filename)


def organization_verification_upload_to(instance, filename):
    return ORGANIZATION_VERIFICATION_UPLOAD.dir_upload(instance, filename)
