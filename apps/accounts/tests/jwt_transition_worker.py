# apps/accounts/tests/jwt_transition_worker.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-09.
#

"""One disposable cross-version phase; raw synthetic tokens never leave artifacts.

Called only by scripts/check_jwt_user_transitions.py, in separate interpreters.
Uses the existing isolated settings, test signing key and fixed MySQL socket.
It never loads production settings or accepts a database URL/signing key.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

MARKER = "townlit-synthetic-jwt-acceptance-v1"
PASSWORD = "SyntheticOldPassword42!"
NEW_PASSWORD = "SyntheticNewPassword43!"


def bootstrap():
    from apps.ai_gateway.tests.run import configure_synthetic_data_protection

    os.environ.clear()
    configure_synthetic_data_protection()
    os.environ["DJANGO_SETTINGS_MODULE"] = "apps.ai_gateway.tests.settings_backend"
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"

    def deny_io(event, args):
        if event == "subprocess.Popen" and args[1] == [
            "/bin/sh",
            "-c",
            "git log --pretty=format:%ct --quiet -1 HEAD",
        ]:
            return
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
            raise RuntimeError("JWT acceptance prohibits external I/O")

    sys.addaudithook(deny_io)
    import django
    from django.conf import settings

    # Use only the already-created disposable TEST schema, not even the
    # isolated runner's default database. No production settings or overrides.
    db = settings.DATABASES["default"]
    assert db["NAME"] == "townlit_b1_disposable"
    assert db["HOST"].endswith("/b1-mysql-socket/mysqld.sock")
    db["NAME"] = "test_townlit_b1_disposable"
    django.setup()
    # Existing post-save hooks enqueue trust work. Bind them to the same
    # isolated in-memory Celery configuration the HTTP test runner uses;
    # never let the default unconfigured app try its AMQP fallback.
    from townlit_b.celery import app as celery_app

    celery_app.set_current()
    celery_app.set_default()
    assert celery_app.conf.broker_url == "memory://"
    assert not celery_app.conf.task_always_eager
    from django.db import connection

    assert connection.vendor == "mysql"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM django_migrations WHERE app=%s AND name=%s",
            ["accounts", "0105_user_auth_session_state"],
        )
        assert cursor.fetchone()[0] == 1, "Real accounts.0105 migration required"


def write_private(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(data, output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    args = parser.parse_args()
    request = json.loads(args.request.read_text())
    assert request["marker"] == MARKER
    bootstrap()

    import rest_framework_simplejwt
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import override_settings
    from rest_framework.exceptions import AuthenticationFailed
    from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )
    from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

    from apps.accounts.authentication import SessionGenerationJWTAuthentication
    from apps.accounts.services.email_lookup import user_email_q
    from apps.accounts.services.password_reset_tokens import (
        issue_password_reset_token_v2,
    )
    from apps.accounts.services.session_jwt import issue_session_refresh_token
    from apps.accounts.services.session_security import (
        get_session_generation,
        increment_session_generation,
    )
    from apps.accounts.views.auth_views import AuthViewSet
    from apps.core.websocket.access_auth import validate_access_token_for_websocket

    version = rest_framework_simplejwt.__version__
    assert version == request["expected_version"]
    key_hash = hashlib.sha256(settings.SIMPLE_JWT["SIGNING_KEY"].encode()).hexdigest()
    User = get_user_model()
    results = []

    for task in request["tasks"]:
        path = args.request.parent / task["fixture"]
        action = task["action"]
        with override_settings(
            AUTH_SESSION_GENERATION_ENFORCE=task.get("enforce", True),
            AUTH_PASSWORD_SECURITY_V2_ENABLED=True,
        ):
            if action == "issue":
                email = f"jwt-gate-{task['case'].lower()}@example.invalid"
                assert not User.objects.filter(user_email_q(email)).exists(), (
                    "Use fresh task artifacts/schema"
                )
                user = User.objects.create_user(email=email, password=PASSWORD)
                user.is_active = True
                user.save(update_fields=["is_active"])
                token = (
                    RefreshToken.for_user(user)
                    if task.get("legacy")
                    else issue_session_refresh_token(user)
                )
                fixture = {
                    "marker": MARKER,
                    "case": task["case"],
                    "user_pk": user.pk,
                    "email": email,
                    "key_hash": key_hash,
                    "issuer": version,
                    "refresh": str(token),
                    "access": str(token.access_token),
                    "claim_type": type(token["user_id"]).__name__,
                    "legacy": task.get("legacy", False),
                }
                write_private(path, fixture)
                results.append(
                    {
                        "case": task["case"],
                        "action": action,
                        "claim_type": fixture["claim_type"],
                    }
                )
                continue

            fixture = json.loads(path.read_text())
            assert fixture["marker"] == MARKER and fixture["key_hash"] == key_hash
            assert fixture["email"].startswith("jwt-gate-") and fixture[
                "email"
            ].endswith("@example.invalid")
            user = User.objects.get(
                user_email_q(fixture["email"]), pk=fixture["user_pk"]
            )
            if action in {"refresh", "deny"}:
                old = fixture["refresh"]
                if task.get("ensure_unblacklisted"):
                    RefreshToken(old)  # generation denial must not be blacklist denial
                    assert get_session_generation(user.pk) == 1
                if action == "refresh":
                    original = RefreshToken(old)
                    old_jti = original["jti"]
                    if not fixture["legacy"]:
                        assert original["tl_sg"] == 0
                response = APIClient().post(
                    "/api/token/refresh/", {"refresh": old}, format="json"
                )
                if action == "deny":
                    assert response.status_code == 401, (
                        f"{fixture['case']}: denial status {response.status_code}"
                    )
                    assert (
                        "access" not in response.data and "refresh" not in response.data
                    )
                    results.append(
                        {"case": fixture["case"], "action": action, "status": 401}
                    )
                    continue
                assert response.status_code == 200, (
                    f"{fixture['case']}: refresh status {response.status_code}"
                )
                rotated = RefreshToken(response.data["refresh"])
                access = AccessToken(response.data["access"])
                assert rotated["jti"] != old_jti
                assert type(rotated["user_id"]).__name__ == fixture["claim_type"]
                assert rotated["user_id"] == original["user_id"]
                assert (
                    ("tl_sg" not in rotated)
                    if fixture["legacy"]
                    else rotated["tl_sg"] == 0
                )
                assert BlacklistedToken.objects.filter(token__jti=old_jti).exists()
                row = OutstandingToken.objects.filter(jti=rotated["jti"]).first()
                assert (row is not None) == (version == "5.5.1")
                if row is not None:
                    assert row.user_id == user.pk and row.created_at is not None
                assert (
                    SessionGenerationJWTAuthentication().get_user(access).pk == user.pk
                )
                # Preserve the consumed token in a separate synthetic-only fixture.
                consumed = dict(fixture)
                write_private(path.with_name(path.stem + "-consumed.json"), consumed)
                fixture.update(refresh=str(rotated), access=str(access))
                write_private(path, fixture)
                results.append(
                    {
                        "case": fixture["case"],
                        "action": action,
                        "status": 200,
                        "claim_type": fixture["claim_type"],
                        "outstanding_immediate": row is not None,
                    }
                )
            elif action == "race":
                import threading
                from unittest.mock import patch

                from django.db import close_old_connections
                from django.urls import get_resolver

                get_resolver().url_patterns  # resolve URLs before starting both consumers
                original_check = RefreshToken.check_blacklist
                barrier = threading.Barrier(2)
                counts = threading.local()
                replies, errors = [], []

                def synchronized_check(token):
                    original_check(token)
                    counts.calls = getattr(counts, "calls", 0) + 1
                    if counts.calls == 2:  # parent's verify, after boundary verify
                        barrier.wait(timeout=15)

                def consume():
                    close_old_connections()
                    try:
                        response = APIClient().post(
                            "/api/token/refresh/",
                            {"refresh": fixture["refresh"]},
                            format="json",
                        )
                        replies.append(response)
                    except Exception as exc:
                        errors.append(type(exc).__name__)
                    finally:
                        close_old_connections()

                with patch.object(RefreshToken, "check_blacklist", synchronized_check):
                    threads = [threading.Thread(target=consume) for _ in range(2)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=30)
                    assert not any(thread.is_alive() for thread in threads)
                assert not errors, "Concurrent refresh raised an exception"
                assert sorted(reply.status_code for reply in replies) == [200, 200], (
                    "Re-review upstream concurrent-consumption semantics"
                )
                child_jtis = set()
                for index, response in enumerate(replies):
                    child = dict(
                        fixture,
                        refresh=response.data["refresh"],
                        access=response.data["access"],
                    )
                    child_jtis.add(RefreshToken(child["refresh"])["jti"])
                    write_private(
                        path.with_name(path.stem + f"-race-{index}.json"), child
                    )
                assert len(child_jtis) == 2
                results.append(
                    {
                        "case": fixture["case"],
                        "action": action,
                        "two_distinct_live_children": True,
                        "statuses": [200, 200],
                    }
                )
            elif action == "revoke":
                assert increment_session_generation(user.pk) == 1
                results.append(
                    {"case": fixture["case"], "action": action, "generation": 1}
                )
            elif action == "prepare_reset":
                from datetime import timedelta

                from django.utils import timezone

                from apps.accounts.views.auth_views import cipher_suite

                if task["format"] == "legacy":
                    bearer = cipher_suite.encrypt(user.email.encode()).decode()
                    verifier = bearer
                else:
                    bearer, verifier = issue_password_reset_token_v2()
                user.reset_token = verifier
                user.reset_token_expiration = timezone.now() + timedelta(minutes=5)
                user.save(update_fields=["reset_token", "reset_token_expiration"])
                fixture["reset_bearer"] = bearer
                write_private(path, fixture)
                results.append(
                    {
                        "case": fixture["case"],
                        "action": action,
                        "format": task["format"],
                    }
                )
            elif action in {"consume_reset", "consume_reset_denied"}:
                req = APIRequestFactory().post(
                    "/synthetic/reset/", {"new_password": NEW_PASSWORD}, format="json"
                )
                response = AuthViewSet.as_view({"post": "reset_password"})(
                    req, reset_token=fixture["reset_bearer"]
                )
                expected = 404 if action == "consume_reset_denied" else 200
                assert response.status_code == expected, (
                    f"Reset transition status {response.status_code}"
                )
                assert "access" not in response.data and "refresh" not in response.data
                if expected == 200:
                    assert response.data.get("login_required") is True
                    user.refresh_from_db()
                    assert (
                        user.check_password(NEW_PASSWORD) and user.reset_token is None
                    )
                results.append(
                    {"case": fixture["case"], "action": action, "status": expected}
                )
            elif action in {"password_change", "password_reset"}:
                factory = APIRequestFactory()
                if action == "password_change":
                    req = factory.post(
                        "/synthetic/change/",
                        {"old_password": PASSWORD, "new_password": NEW_PASSWORD},
                        format="json",
                    )
                    force_authenticate(req, user=user)
                    response = AuthViewSet.as_view({"post": "change_password"})(req)
                else:
                    bearer, verifier = issue_password_reset_token_v2()
                    user.reset_token = verifier
                    from datetime import timedelta

                    from django.utils import timezone

                    user.reset_token_expiration = timezone.now() + timedelta(minutes=5)
                    user.save(update_fields=["reset_token", "reset_token_expiration"])
                    req = factory.post(
                        "/synthetic/reset/",
                        {"new_password": NEW_PASSWORD},
                        format="json",
                    )
                    response = AuthViewSet.as_view({"post": "reset_password"})(
                        req, reset_token=bearer
                    )
                assert (
                    response.status_code == 200
                    and response.data.get("login_required") is True
                )
                assert "access" not in response.data and "refresh" not in response.data
                user.refresh_from_db()
                assert user.check_password(NEW_PASSWORD)
                results.append(
                    {"case": fixture["case"], "action": action, "login_required": True}
                )
            elif action == "deny_access":
                access = AccessToken(fixture["access"])
                try:
                    SessionGenerationJWTAuthentication().get_user(access)
                except AuthenticationFailed as exc:
                    assert exc.get_codes() == "session_revoked"
                else:
                    raise AssertionError("Revoked access accepted")
                assert validate_access_token_for_websocket(fixture["access"]) is None
                results.append(
                    {
                        "case": fixture["case"],
                        "action": action,
                        "rest_and_ws_denied": True,
                    }
                )
            else:
                raise ValueError("Unknown fixed test phase")

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations")
        migrations = cursor.fetchone()[0]
    print(
        "JWT_GATE_RESULT "
        + json.dumps(
            {
                "version": version,
                "signing_key_fingerprint": key_hash,
                "applied_migrations": migrations,
                "results": results,
            }
        )
    )


if __name__ == "__main__":
    main()
