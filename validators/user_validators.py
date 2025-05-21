import re
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

def validate_phone_number(value):
    pattern = r'^\+?[1-9]\d{1,14}$'
    if not re.fullmatch(pattern, value):
        raise ValidationError("Phone number must be in international format.")

def validate_email_field(value):
    try:
        validate_email(value)
    except ValidationError:
        raise ValidationError("Invalid email format.")

def validate_password_field(value):
    if len(value) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not any(char.isdigit() for char in value):
        raise ValidationError("Password must contain at least one digit.")
    if not any(char.isalpha() for char in value):
        raise ValidationError("Password must contain at least one letter.")
