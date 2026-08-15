# apps/content_safety/exceptions.py
#
# TownLIT
#
# Created by Hossein Sakkaki on 2026-08-13.
# Last Update by Hossein Sakkaki on 2026-08-13.

from rest_framework import status
from rest_framework.exceptions import (
    APIException,
)


class ContentSafetyBlockedError(
    APIException
):
    status_code = (
        status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    default_code = (
        "content_safety_blocked"
    )

    def __init__(
        self,
        *,
        reason_code: str,
    ):
        super().__init__(
            detail={
                "code": (
                    "content_safety_blocked"
                ),
                "decision": "block",
                "reason_code": reason_code,
                "retryable": False,
            }
        )


class ContentSafetyReviewError(
    APIException
):
    status_code = (
        status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    default_code = (
        "content_safety_review_required"
    )

    def __init__(
        self,
        *,
        reason_code: str,
    ):
        super().__init__(
            detail={
                "code": (
                    "content_safety_review_required"
                ),
                "decision": "review",
                "reason_code": reason_code,
                "retryable": True,
            }
        )


class ContentSafetyUnavailableError(
    APIException
):
    status_code = (
        status.HTTP_503_SERVICE_UNAVAILABLE
    )

    default_code = (
        "content_safety_unavailable"
    )

    def __init__(self):
        super().__init__(
            detail={
                "code": (
                    "content_safety_unavailable"
                ),
                "decision": "review",
                "reason_code": (
                    "provider_unavailable"
                ),
                "retryable": True,
            }
        )