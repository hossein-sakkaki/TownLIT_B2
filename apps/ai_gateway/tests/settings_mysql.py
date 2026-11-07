# apps/ai_gateway/tests/settings_mysql.py
# TownLIT-Backend
# Created by Codex on 2026-11-06.
# Last Update by Codex on 2026-11-06.

"""Disposable local socket only; no environment-supplied hosts or credentials."""

from pathlib import Path

from .settings import *  # noqa: F403


SOCKET = Path(__file__).resolve().parents[4] / "b1-mysql-socket" / "mysqld.sock"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.mysql",
    "HOST": str(SOCKET), "PORT": "", "USER": "root", "PASSWORD": "",
    "NAME": "townlit_b1_disposable",
    "TEST": {"NAME": "test_townlit_b1_gateway"},
    "OPTIONS": {"charset": "utf8mb4", "isolation_level": "read committed",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'"},
}}
