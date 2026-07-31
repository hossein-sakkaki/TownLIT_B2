# apps/audio_catalog/checks.py
from django.conf import settings
from django.core.checks import Error, register

@register()
def audio_catalog_settings_check(app_configs, **kwargs):
    errors = []
    if not getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""):
        errors.append(Error("AWS_STORAGE_BUCKET_NAME is required.", id="audio_catalog.E001"))
    if not getattr(settings, "ASSET_CDN_BASE_URL", ""):
        errors.append(Error("ASSET_CDN_BASE_URL is required.", id="audio_catalog.E002"))
    return errors
