# apps/ai_gateway/tests/settings.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""In-memory fixtures only; never import production settings or read .env files."""

SECRET_KEY = "synthetic-b1-test-key-not-a-credential"
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
INSTALLED_APPS = ["apps.ai_gateway"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
ROOT_URLCONF = "apps.ai_gateway.tests.urls"
MIDDLEWARE = ["django.middleware.csrf.CsrfViewMiddleware"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
AI_GATEWAY_ENABLED = False
AI_GATEWAY_ENVIRONMENT = "synthetic"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
STORAGES = {"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}
