# scripts/check_jwt_user_transitions.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.
#

"""Execute real library transitions against an already-migrated disposable MySQL.

Run outside Django's isolated runner so each phase can launch a fresh interpreter.
Workers themselves clear credentials, use fixed test settings/database/key and
prohibit outbound I/O. Artifacts contain ONLY synthetic tokens; never commit or
upload them. A successful run is bounded evidence, not production acceptance.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "townlit-synthetic-jwt-acceptance-v1"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-python", required=True, type=Path)
    parser.add_argument("--supported-python", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit("Synthetic token artifacts must be outside the repository")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    interpreters = {
        "5.3.1": args.baseline_python.absolute(),
        "5.5.1": args.supported_python.absolute(),
    }
    phases = []

    def phase(name, version, tasks):
        request = output / f"{len(phases):02d}-{name}.json"
        request.write_text(
            json.dumps({"marker": MARKER, "expected_version": version, "tasks": tasks})
        )
        os.chmod(request, 0o600)
        completed = subprocess.run(
            [
                str(interpreters[version]),
                "-m",
                "apps.accounts.tests.jwt_transition_worker",
                str(request),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        (output / f"{request.stem}.log").write_text(completed.stdout + completed.stderr)
        if completed.returncode:
            raise SystemExit(
                f"Phase {name} failed; inspect task-owned {request.stem}.log (synthetic data only)"
            )
        lines = [
            line
            for line in completed.stdout.splitlines()
            if line.startswith("JWT_GATE_RESULT ")
        ]
        if len(lines) != 1:
            raise SystemExit(f"Missing result for {name}")
        result = json.loads(lines[0].split(" ", 1)[1])
        if phases:
            assert (
                result["signing_key_fingerprint"]
                == phases[0]["result"]["signing_key_fingerprint"]
            )
            assert (
                result["applied_migrations"]
                == phases[0]["result"]["applied_migrations"]
            )
        phases.append({"phase": name, "version": version, "result": result})
        print(f"PASS {name}: SimpleJWT {version}, {len(tasks)} checks", flush=True)

    plans = {
        "A": ("5.3.1", "5.3.1"),
        "B": ("5.3.1", "5.5.1"),
        "C": ("5.5.1", "5.5.1"),
        "D": ("5.5.1", "5.3.1"),
    }
    kinds = ("survival", "generation", "password_change", "password_reset")
    for issuer in interpreters:
        phase(
            "issue-" + issuer,
            issuer,
            [
                {
                    "action": "issue",
                    "fixture": f"{case}-{kind}.json",
                    "case": f"{case}-{kind}",
                }
                for case, (origin, _) in plans.items()
                if origin == issuer
                for kind in kinds
            ],
        )
    for consumer in interpreters:
        phase(
            "rotate-" + consumer,
            consumer,
            [
                {"action": "refresh", "fixture": f"{case}-{kind}.json"}
                for case, (_, target) in plans.items()
                if target == consumer
                for kind in kinds
            ],
        )
    for consumer in interpreters:
        phase(
            "blacklist-persistence-" + consumer,
            consumer,
            [
                {"action": "deny", "fixture": f"{case}-{kind}-consumed.json"}
                for case in plans
                for kind in kinds
            ],
        )
    for consumer in interpreters:
        phase(
            "mutate-password-or-generation-" + consumer,
            consumer,
            [
                {
                    "action": "revoke" if kind == "generation" else kind,
                    "fixture": f"{case}-{kind}.json",
                }
                for case, (_, target) in plans.items()
                if target == consumer
                for kind in kinds
                if kind != "survival"
            ],
        )
    for consumer in interpreters:
        phase(
            "revocation-across-profiles-" + consumer,
            consumer,
            [
                {
                    "action": action,
                    "fixture": f"{case}-{kind}.json",
                    "ensure_unblacklisted": True,
                }
                for case in plans
                for kind in kinds
                if kind != "survival"
                for action in ("deny", "deny_access")
            ],
        )
    # Surviving refresh chains are actually rotated once more after reversing
    # the library transition; this is not just decoding a hand-edited claim.
    for consumer in interpreters:
        phase(
            "survival-return-to-issuer-" + consumer,
            consumer,
            [
                {"action": "refresh", "fixture": f"{case}-survival.json"}
                for case, (origin, _) in plans.items()
                if origin == consumer
            ],
        )
    for issuer in interpreters:
        label = "E-old" if issuer == "5.3.1" else "E-new"
        phase(
            "legacy-issue-" + issuer,
            issuer,
            [
                {
                    "action": "issue",
                    "fixture": label + ".json",
                    "case": label,
                    "legacy": True,
                }
            ],
        )
    for index, version in enumerate(interpreters):
        for enforce in (False, True):
            phase(
                f"legacy-zero-{index}-{enforce}",
                version,
                [
                    {
                        "action": "refresh",
                        "fixture": label + ".json",
                        "enforce": enforce,
                    }
                    for label in ("E-old", "E-new")
                ],
            )
    phase(
        "legacy-first-revocation",
        "5.5.1",
        [
            {"action": "revoke", "fixture": label + ".json"}
            for label in ("E-old", "E-new")
        ],
    )
    for version in interpreters:
        phase(
            "legacy-enforcement-off-after-revocation-" + version,
            version,
            [
                {"action": "refresh", "fixture": label + ".json", "enforce": False}
                for label in ("E-old", "E-new")
            ],
        )
        phase(
            "legacy-enforcement-on-after-revocation-" + version,
            version,
            [
                {
                    "action": action,
                    "fixture": label + ".json",
                    "ensure_unblacklisted": True,
                }
                for label in ("E-old", "E-new")
                for action in ("deny", "deny_access")
            ],
        )
    for version in interpreters:
        label = "race-old" if version == "5.3.1" else "race-new"
        phase(
            "race-issue-" + version,
            version,
            [{"action": "issue", "fixture": label + ".json", "case": label}],
        )
        phase(
            "concurrent-refresh-characterization-" + version,
            version,
            [{"action": "race", "fixture": label + ".json"}],
        )
        phase(
            "revoke-race-children-" + version,
            version,
            [{"action": "revoke", "fixture": label + ".json"}],
        )
    for consumer in interpreters:
        phase(
            "race-children-revoked-" + consumer,
            consumer,
            [
                {
                    "action": action,
                    "fixture": f"{label}-race-{index}.json",
                    "ensure_unblacklisted": True,
                }
                for label in ("race-old", "race-new")
                for index in (0, 1)
                for action in ("deny", "deny_access")
            ],
        )
    summary = {
        "marker": MARKER,
        "result": "PASS",
        "scenario_transitions": plans,
        "phases": phases,
        "limits": [
            "synthetic users/keys only",
            "fixed disposable MySQL; schema retained through library rollback",
            "concurrency deliberately synchronized after blacklist verification",
            "no live clients, production release or capacity acceptance",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"PASS {len(phases)} separate-process phases; public result summary: {output / 'summary.json'}"
    )


if __name__ == "__main__":
    main()
