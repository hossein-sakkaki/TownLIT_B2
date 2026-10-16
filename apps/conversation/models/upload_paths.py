# apps/conversation/models/upload_paths.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-10-06.
# Last Update by Hossein Sakkaki on 2026-10-06.
#


def get_upload_path(category, file_type, sub_folder):
    """ Import FileUpload dynamically to avoid circular import issues. """
    from utils.common.utils import FileUpload
    return FileUpload(category, file_type, sub_folder).dir_upload
