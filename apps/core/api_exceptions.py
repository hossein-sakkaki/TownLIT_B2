# apps/core/api_exceptions.py
from rest_framework.exceptions import APIException

class SuspendedAccount(APIException):
    status_code = 423  # Locked
    default_detail = (
        "Your account is temporarily suspended for a Sanctuary review. "
        "This protective step helps keep you and the community safe. "
        "Access may be restored once the review completes."
    )
    default_code = "account_suspended"

class DeletedAccount(APIException):
    status_code = 403
    default_detail = (
        "Your account is currently deactivated. "
        "You can reactivate your account within 1 year using your reactivation code."
    )
    default_code = "account_deleted"
