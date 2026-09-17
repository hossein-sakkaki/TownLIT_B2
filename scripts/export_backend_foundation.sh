#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/00_backend_project_foundation.md"

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Project Foundation Snapshot" \
    "Django project structure, installed applications, Python dependencies, settings architecture, URL routing, ASGI/WSGI/Celery entrypoints, model inventory and deployment/build foundation."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Directory structure
# ============================================================

separator "$OUTPUT_FILE" "PROJECT DIRECTORY STRUCTURE"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path "$ROOT_DIR/.git" \
            -o -path "$ROOT_DIR/.venv" \
            -o -path "$ROOT_DIR/venv" \
            -o -path "$ROOT_DIR/env" \
            -o -path "$ROOT_DIR/__pycache__" \
            -o -path "$ROOT_DIR/node_modules" \
            -o -path "$ROOT_DIR/staticfiles" \
            -o -path "$ROOT_DIR/media" \
            -o -path "$ROOT_DIR/chatgpt_sources" \
            -o -path '*/__pycache__' \
            -o -path '*/migrations' \
        \) -prune \
        -o -maxdepth 6 -type d -print \
        | sed "s|$ROOT_DIR|.|" \
        | sort

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Dependency / tooling configuration
# ============================================================

separator "$OUTPUT_FILE" "PYTHON DEPENDENCY AND TOOLING CONFIGURATION"

for candidate in \
    "$ROOT_DIR/pyproject.toml" \
    "$ROOT_DIR/poetry.lock" \
    "$ROOT_DIR/Pipfile" \
    "$ROOT_DIR/Pipfile.lock" \
    "$ROOT_DIR/setup.py" \
    "$ROOT_DIR/setup.cfg" \
    "$ROOT_DIR/tox.ini" \
    "$ROOT_DIR/pytest.ini" \
    "$ROOT_DIR/manage.py" \
    "$ROOT_DIR/Makefile" \
    "$ROOT_DIR/Dockerfile" \
    "$ROOT_DIR/docker-compose.yml" \
    "$ROOT_DIR/docker-compose.yaml"
do
    append_file "$OUTPUT_FILE" "$candidate"
done

find "$ROOT_DIR" \
    -maxdepth 3 \
    -type f \
    \( \
        -name "requirements.txt" \
        -o -name "requirements-*.txt" \
        -o -name "*requirements*.txt" \
    \) \
    -print \
    | sort \
    | while IFS= read -r file
do
    append_file "$OUTPUT_FILE" "$file"
done

# ============================================================
# Environment templates only — NEVER .env
# ============================================================

separator "$OUTPUT_FILE" "ENVIRONMENT TEMPLATE INVENTORY"

{
    echo '```text'

    find "$ROOT_DIR" \
        -maxdepth 4 \
        -type f \
        \( \
            -name ".env.example" \
            -o -name ".env.sample" \
            -o -name ".env.template" \
            -o -name "env.example" \
        \) \
        -print \
        | sed "s|$ROOT_DIR|.|" \
        | sort

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Django applications
# ============================================================

separator "$OUTPUT_FILE" "DJANGO APP INVENTORY"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path '*/.venv/*' \
            -o -path '*/venv/*' \
            -o -path '*/__pycache__/*' \
            -o -path '*/migrations/*' \
        \) -prune \
        -o -type f -name "apps.py" -print \
        | sed "s|$ROOT_DIR/||" \
        | sort

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Settings files — redacted
# ============================================================

separator "$OUTPUT_FILE" "DJANGO SETTINGS"

find "$ROOT_DIR" \
    \( \
        -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/__pycache__/*' \
    \) -prune \
    -o -type f \
    \( \
        -name "settings.py" \
        -o -path '*/settings/*.py' \
    \) \
    -print \
    | sort \
    | while IFS= read -r file
do
    append_redacted_python_file "$OUTPUT_FILE" "$file"
done

# ============================================================
# Root project entrypoints
# ============================================================

separator "$OUTPUT_FILE" "PROJECT ENTRYPOINTS AND ROUTING"

find "$ROOT_DIR" \
    \( \
        -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/migrations/*' \
        -o -path '*/__pycache__/*' \
    \) -prune \
    -o -type f \
    \( \
        -name "urls.py" \
        -o -name "asgi.py" \
        -o -name "wsgi.py" \
        -o -name "routing.py" \
        -o -name "celery.py" \
    \) \
    -print \
    | sort \
    | while IFS= read -r file
do
    # Keep foundation focused on project-level and app routing.
    append_file "$OUTPUT_FILE" "$file" "python"
done

# ============================================================
# Model class inventory using Python AST
# ============================================================

separator "$OUTPUT_FILE" "DJANGO MODEL CLASS INVENTORY"

python3 - "$ROOT_DIR" >> "$OUTPUT_FILE" <<'PY'
import ast
import os
import sys

root = os.path.abspath(sys.argv[1])

excluded = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "node_modules",
    "staticfiles",
    "media",
    "chatgpt_sources",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

print("```text")

results = []

for current, dirs, files in os.walk(root):
    dirs[:] = [
        d for d in dirs
        if d not in excluded and d != "migrations"
    ]

    for filename in files:
        if not filename.endswith(".py"):
            continue

        if filename != "models.py" and "models" not in current.split(os.sep):
            continue

        path = os.path.join(current, filename)

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                source = f.read()

            tree = ast.parse(source)
        except Exception:
            continue

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            bases = []

            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except Exception:
                    bases.append("?")

            if not bases:
                continue

            base_text = ", ".join(bases)

            likely_model = any(
                marker in base_text
                for marker in (
                    "Model",
                    "AbstractUser",
                    "AbstractBaseUser",
                    "PermissionsMixin",
                )
            )

            if likely_model:
                rel = os.path.relpath(path, root)
                results.append(
                    (rel, node.lineno, node.name, base_text)
                )

for rel, lineno, name, bases in sorted(results):
    print(f"{rel}:{lineno}")
    print(f"  class {name}({bases})")

print("```")
PY

# ============================================================
# Migration inventory, without migration source noise
# ============================================================

separator "$OUTPUT_FILE" "MIGRATION INVENTORY"

{
    echo '```text'

    find "$ROOT_DIR" \
        -type f \
        -path '*/migrations/*.py' \
        ! -name "__init__.py" \
        | sed "s|$ROOT_DIR/||" \
        | sort

    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Backend foundation snapshot created:"
echo "$OUTPUT_FILE"
echo