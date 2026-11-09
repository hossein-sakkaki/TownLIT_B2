# scripts/check_ai_gateway_headers.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Check the established Backend header convention on the B1 source scope."""

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    paths = sorted((ROOT / "apps/ai_gateway").rglob("*.py"))
    paths += [
        ROOT / name
        for name in (
            "api/v1/api_urls.py",
            "townlit_b/settings.py",
            "scripts/check_ai_gateway_headers.py",
            ".github/workflows/ai-gateway-b1.yml",
        )
    ]
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        pattern = (
            r"\A# " + re.escape(relative) + r"\n# TownLIT-Backend\n#\n"
            r"# Created by Hossein Sakkaki on (\d{4}-\d{2}-\d{2})\.\n"
            r"# Last Update by Hossein Sakkaki on (\d{4}-\d{2}-\d{2})\.\n#\n"
        )
        match = re.match(pattern, path.read_text())
        if match is None:
            raise SystemExit(f"Malformed TownLIT header: {relative}")
        created, updated = (date.fromisoformat(value) for value in match.groups())
        if updated < created:
            raise SystemExit(f"Update predates creation: {relative}")
    print(f"PASS: {len(paths)} B1 TownLIT source headers")


if __name__ == "__main__":
    main()
