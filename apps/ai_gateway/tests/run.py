# apps/ai_gateway/tests/run.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-09.
#

"""Run isolated B1 checks with inherited credentials and outbound I/O disabled."""

import json
import os
import sys


def configure_synthetic_data_protection():
    """Fixed public test keys for checkpoint encrypted-only account fixtures."""
    key = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    for prefix in ("TOWNLIT_DP_FERNET", "TOWNLIT_DP_BLIND_INDEX"):
        os.environ[prefix + "_KEYS_JSON"] = json.dumps({"synthetic": key})
    os.environ["TOWNLIT_DP_ACTIVE_KEY_ID"] = "synthetic"
    os.environ["TOWNLIT_DP_BLIND_INDEX_ACTIVE_KEY_ID"] = "synthetic"


def main():
    profiles = {
        "core": "settings",
        "mysql": "settings_mysql",
        "backend": "settings_backend",
    }
    if len(sys.argv) < 3 or sys.argv[1] not in profiles:
        raise SystemExit(
            "Usage: python -m apps.ai_gateway.tests.run core|mysql|backend <Django command>"
        )
    if any(arg.startswith("--settings") for arg in sys.argv[2:]):
        raise SystemExit("Settings overrides are prohibited by the isolated runner.")
    if sys.argv[2] not in {
        "test",
        "check",
        "makemigrations",
        "migrate",
        "showmigrations",
    }:
        raise SystemExit("Only isolated test and migration checks are supported.")
    profile = profiles[sys.argv[1]]
    os.environ.clear()
    configure_synthetic_data_protection()
    os.environ["DJANGO_SETTINGS_MODULE"] = "apps.ai_gateway.tests." + profile
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"

    def deny_external_io(event, args):
        if event == "subprocess.Popen" and args[1] == [
            "/bin/sh",
            "-c",
            "git log --pretty=format:%ct --quiet -1 HEAD",
        ]:
            return  # Django dependency version metadata, no remote access.
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen"}:
            raise RuntimeError("B1 tests prohibit outbound network and subprocesses")

    sys.addaudithook(deny_external_io)
    # mysqlclient uses the fixed disposable Unix socket, not Python sockets.
    from django.core.management import execute_from_command_line

    execute_from_command_line([sys.argv[0], *sys.argv[2:]])


if __name__ == "__main__":
    main()
