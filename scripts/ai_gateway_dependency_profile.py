# scripts/ai_gateway_dependency_profile.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by OpenAI Codex on 2026-11-07.
#

"""Reproduce PR #6 profiles for the focused refresh repair; never edit production pins.

Usage: python scripts/ai_gateway_dependency_profile.py baseline|supported
Pipe output to a task-owned file and install in a new venv for that profile.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "cffi": "1.17.1",
    "cryptography": "43.0.1",
    "pyOpenSSL": "24.2.1",
    "PyJWT": "2.8.0",
    "djangorestframework-simplejwt": "5.3.1",
}
COMMON = {
    "cffi": "2.1.1",
    "cryptography": "50.0.2",
    "pyOpenSSL": "26.4.0",
    "PyJWT": "2.15.1",
}


def manifest(profile):
    if profile not in {"baseline", "supported"}:
        raise ValueError("Unknown disposable dependency profile")
    source = (ROOT / "requirements.txt").read_text()
    for name, expected in EXPECTED.items():
        if source.splitlines().count(f"{name}=={expected}") != 1:
            raise ValueError("Baseline dependency drift; re-review the matrix")
    if profile == "baseline":
        return source
    replacements = dict(COMMON)
    replacements["djangorestframework-simplejwt"] = "5.5.1"
    for name, target in replacements.items():
        source = source.replace(f"{name}=={EXPECTED[name]}\n", f"{name}=={target}\n")
    return source.rstrip() + "\njoserfc==1.8.0\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.write(manifest(sys.argv[1]))
