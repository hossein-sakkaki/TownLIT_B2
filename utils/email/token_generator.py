from django.core.exceptions import ObjectDoesNotExist
from django.core import signing

from apps.communication.models import ExternalContact
from apps.moderation.models import AccessRequest 
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# -----------------------------------------------------------------------------------------------
EMAIL_OPT_TOKEN_SALT = "email-opt-token"

def generate_email_opt_token(user_id: int) -> str:
    """
    Generates a signed token for email actions (e.g., unsubscribe/resubscribe)
    based on the primary key (ID) of a user-related model.
    """
    return signing.dumps(user_id, salt=EMAIL_OPT_TOKEN_SALT)

def decode_email_opt_token(token: str) -> int:
    """
    Decodes the email token and returns the original ID.
    Tokens expire after 7 days (in seconds).
    """
    return signing.loads(token, salt=EMAIL_OPT_TOKEN_SALT, max_age=60 * 60 * 24 * 7)

def validate_email_opt_token(token: str):
    """
    Validates a token by trying to retrieve the corresponding user object.
    
    ✅ Supports:
    - CustomUser (standard registered users)
    - AccessRequest (temporary pre-registration entries — will be removed in the future)

    ❗ This function will return None if:
    - The token is invalid or expired
    - No matching object is found
    """
    try:
        user_id = decode_email_opt_token(token)
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            # Temporary support for invite emails sent to AccessRequest entries
            return AccessRequest.objects.get(pk=user_id)
    except (signing.BadSignature, signing.SignatureExpired, ObjectDoesNotExist):
        return None


# -----------------------------------------------------------------------------------------------
EXTERNAL_EMAIL_UNSUBSCRIBE_SALT = "external-email-unsub"

def generate_external_email_token(email: str) -> str:
    return signing.dumps(email, salt=EXTERNAL_EMAIL_UNSUBSCRIBE_SALT)

def decode_external_email_token(token: str) -> str:
    return signing.loads(token, salt=EXTERNAL_EMAIL_UNSUBSCRIBE_SALT, max_age=60 * 60 * 24 * 7)

def validate_external_email_token(token: str):
    try:
        email = decode_external_email_token(token)
        return ExternalContact.objects.get(email__iexact=email, is_unsubscribed=False)
    except (signing.BadSignature, signing.SignatureExpired, ObjectDoesNotExist):
        return None
