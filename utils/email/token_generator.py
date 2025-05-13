from django.core.exceptions import ObjectDoesNotExist
from django.core import signing
from apps.communication.models import ExternalContact
from django.contrib.auth import get_user_model

CustomUser = get_user_model()



# -----------------------------------------------------------------------------------------------
EMAIL_OPT_TOKEN_SALT = "email-opt-token"

def generate_email_opt_token(user_id: int) -> str:
    return signing.dumps(user_id, salt=EMAIL_OPT_TOKEN_SALT)

def decode_email_opt_token(token: str) -> int:
    return signing.loads(token, salt=EMAIL_OPT_TOKEN_SALT, max_age=60 * 60 * 24 * 7)

def validate_email_opt_token(token: str):
    try:
        user_id = decode_email_opt_token(token)
        return CustomUser.objects.get(pk=user_id)
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
