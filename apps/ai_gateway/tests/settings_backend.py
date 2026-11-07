# apps/ai_gateway/tests/settings_backend.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Isolated baseline regression settings; never execute settings.py or load .env.

    Read only literal app/middleware/REST declarations from the checked-out
    baseline. No Firebase credential fixture stands in for a real connection.
"""

import ast
from datetime import timedelta
from pathlib import Path

from .settings_mysql import *  # noqa: F403


BASE_DIR = Path(__file__).resolve().parents[3]
DATABASES["default"]["TEST"] = {"NAME": "test_townlit_b1_disposable"}  # noqa: F405
_tree = ast.parse((BASE_DIR / "townlit_b" / "settings.py").read_text())
_assignments = {target.id: node.value for node in _tree.body if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Name)}


def _test_value(node):
    """Resolve only literal configuration and the baseline's timedelta values."""
    if isinstance(node, ast.Name):
        return {"SECRET_KEY": SECRET_KEY, "CRYPTO_THROTTLE_RATE": "30/min",  # noqa: F405
                "CRYPTO_HEAVY_THROTTLE_RATE": "10/min"}[node.id]
    if isinstance(node, ast.Dict):
        return {_test_value(key): _test_value(value) for key, value in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_test_value(value) for value in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_test_value(value) for value in node.elts)
    if isinstance(node, ast.Call):
        if (not isinstance(node.func, ast.Name) or node.func.id != "timedelta" or node.args
                or any(item.arg not in {"days", "minutes"} or type(ast.literal_eval(item.value)) is not int
                       for item in node.keywords)):
            raise ValueError("Unsupported baseline test declaration")
        return timedelta(**{item.arg: ast.literal_eval(item.value) for item in node.keywords})
    return ast.literal_eval(node)


INSTALLED_APPS = ast.literal_eval(_assignments["INSTALLED_APPS"])
MIDDLEWARE = ast.literal_eval(_assignments["MIDDLEWARE"])
REST_FRAMEWORK = _test_value(_assignments["REST_FRAMEWORK"])
CORS_URLS_REGEX = ast.literal_eval(_assignments["CORS_URLS_REGEX"])
AUTH_USER_MODEL = ast.literal_eval(_assignments["AUTH_USER_MODEL"])
SIMPLE_JWT = _test_value(_assignments["SIMPLE_JWT"])
AUTH_SESSION_GENERATION_ENFORCE = False
AUTH_PASSWORD_SECURITY_V2_ENABLED = False
PASSWORD_RESET_TOKEN_V2_ISSUE = False
ROOT_URLCONF = "townlit_b.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "APP_DIRS": True,
              "OPTIONS": {"context_processors": [
                  "django.template.context_processors.request",
                  "django.contrib.auth.context_processors.auth",
                  "django.contrib.messages.context_processors.messages",
              ]}}]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = str(BASE_DIR.parent / "b1-disposable-media")
SITE_URL = "https://synthetic.example.invalid"
FRONTEND_BASE_URL = SITE_URL
PASSWORD_RESET_FRONTEND_URL = SITE_URL
FERNET_KEY = b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
MASTER_KEY = FERNET_KEY
DJANGO_CRYPTO_KEY = FERNET_KEY
CRYPTOGRAPHY_KEY = FERNET_KEY
EMAIL_LOGO_URL = "https://synthetic.example.invalid/logo"
DEFAULT_FROM_EMAIL = "synthetic@example.invalid"
CELERY_TASK_ALWAYS_EAGER = False
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {name: {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
          for name in ("default", "messenger_throttle")}
USE_S3 = False
SERVE_FILES_PUBLICLY = False
FIREBASE_CREDENTIALS = {}
FIREBASE_PROJECT_ID = ""
OPENAI_API_KEY = ""
STRIPE_SECRET_KEY = ""
PAYPAL_CLIENT_ID = ""
PAYPAL_SECRET_KEY = ""
CKEDITOR_UPLOAD_PATH = "synthetic/"
AWS_S3_REGION_NAME = "us-east-1"
AWS_STORAGE_BUCKET_NAME = "synthetic-b1"
AWS_ACCESS_KEY_ID = "synthetic-b1-not-a-credential"
AWS_SECRET_ACCESS_KEY = "synthetic-b1-not-a-credential"
LITSHIELD_ACCESS_EXPIRATION_SECONDS = 300
EMAIL_CODE_EXPIRATION_MINUTES = 10
RESET_LINK_EXPIRATION_MINUTES = 30
DEFAULT_USER_AVATAR_URL = "/synthetic/avatar.png"
ASSET_CDN_BASE_URL = "https://synthetic.example.invalid"
