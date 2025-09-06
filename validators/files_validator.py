# /validators/files_validator.py

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
import datetime

http_https_only = URLValidator(schemes=["http", "https"])

def validate_http_https(value: str):
    if value:
        http_https_only(value)

def soft_date_bounds(d: datetime.date, *, past_years=50, future_years=10):
    if not d:
        return
    today = datetime.date.today()
    min_date = today.replace(year=today.year - past_years)
    max_date = today.replace(year=today.year + future_years)
    if d < min_date or d > max_date:
        raise ValidationError("Date out of acceptable range.")
