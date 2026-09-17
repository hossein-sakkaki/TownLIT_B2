# apps/posts/tests/test_upload_path_contract.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-09-14.
# Last Update by Hossein Sakkaki on 2026-09-14.
#

from django.apps import apps
from django.db import models
from django.test import SimpleTestCase

from utils.common.utils import FileUpload


class PostsUploadPathContractTests(
    SimpleTestCase
):
    def test_posts_file_uploads_do_not_use_bound_dir_upload(self):
        offenders = []

        for model in (
            apps.get_app_config("posts")
            .get_models()
        ):
            for field in model._meta.get_fields():
                if not isinstance(
                    field,
                    models.FileField,
                ):
                    continue

                upload_to = field.upload_to
                bound_owner = getattr(
                    upload_to,
                    "__self__",
                    None,
                )

                if (
                    isinstance(
                        bound_owner,
                        FileUpload,
                    )
                    and getattr(
                        upload_to,
                        "__name__",
                        "",
                    )
                    == "dir_upload"
                ):
                    offenders.append(
                        (
                            f"{model._meta.label}."
                            f"{field.name}"
                        )
                    )

        self.assertEqual(
            offenders,
            [],
            (
                "Posts FileFields must use "
                "deconstructible FileUpload objects "
                "instead of bound dir_upload methods."
            ),
        )