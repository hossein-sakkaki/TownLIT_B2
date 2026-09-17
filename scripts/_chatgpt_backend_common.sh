#!/usr/bin/env bash

set -euo pipefail

# ============================================================
# TownLIT Backend — ChatGPT Snapshot Common Helpers
#
# Shared helper functions used by all backend snapshot exporters.
#
# Security:
# - Never exports .env files.
# - Redacts potentially sensitive Python settings assignments.
# - Skips large individual files automatically.
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ROOT_DIR="$(
    git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null
)"; then
    :
else
    ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"

mkdir -p "$OUTPUT_DIR"

# Maximum size of a single source file automatically embedded.
# Default: 600 KB.
#
# Override example:
#
# CHATGPT_SNAPSHOT_MAX_FILE_BYTES=1000000 \
# ./scripts/export_backend_chatgpt_context.sh
#
MAX_FILE_BYTES="${CHATGPT_SNAPSHOT_MAX_FILE_BYTES:-600000}"


# ============================================================
# Section separator
# ============================================================

separator() {
    local output="$1"
    local title="$2"

    {
        echo
        echo "================================================================"
        echo "$title"
        echo "================================================================"
        echo
    } >> "$output"
}


# ============================================================
# Relative repository path
# ============================================================

relative_path() {
    local file="$1"

    if [[ "$file" == "$ROOT_DIR/"* ]]; then
        echo "${file#$ROOT_DIR/}"
    else
        echo "$file"
    fi
}


# ============================================================
# File size
#
# macOS first, GNU fallback.
# ============================================================

file_size_bytes() {
    local file="$1"

    if stat -f%z "$file" >/dev/null 2>&1; then
        stat -f%z "$file"
    else
        stat -c%s "$file"
    fi
}


# ============================================================
# Markdown code language
# ============================================================

language_for_file() {
    local file="$1"

    case "$file" in
        *.py)
            echo "python"
            ;;

        *.toml)
            echo "toml"
            ;;

        *.json)
            echo "json"
            ;;

        *.yaml|*.yml)
            echo "yaml"
            ;;

        *.ini|*.cfg)
            echo "ini"
            ;;

        *.txt)
            echo "text"
            ;;

        Dockerfile|*/Dockerfile|*.dockerfile)
            echo "dockerfile"
            ;;

        *.sh)
            echo "bash"
            ;;

        *.md)
            echo "markdown"
            ;;

        *.xml)
            echo "xml"
            ;;

        *.html)
            echo "html"
            ;;

        *.css)
            echo "css"
            ;;

        *)
            echo "text"
            ;;
    esac
}


# ============================================================
# Append source file
# ============================================================

append_file() {
    local output="$1"
    local file="$2"
    local language="${3:-}"

    [[ -f "$file" ]] || return 0

    # Safety: never export actual environment files.
    case "$(basename "$file")" in
        .env|.env.local|.env.dev|.env.development|.env.prod|.env.production|.env.staging)
            return 0
            ;;
    esac

    if [[ -z "$language" ]]; then
        language="$(language_for_file "$file")"
    fi

    local relative
    relative="$(relative_path "$file")"

    local size
    size="$(file_size_bytes "$file")"

    {
        echo
        echo "----------------------------------------------------------------"
        echo "FILE: $relative"
        echo "SIZE: $size bytes"
        echo "----------------------------------------------------------------"
        echo
    } >> "$output"

    if (( size > MAX_FILE_BYTES )); then
        {
            echo "> FILE OMITTED FROM FULL SNAPSHOT"
            echo ">"
            echo "> Reason: source file exceeds the automatic snapshot limit."
            echo "> Limit: $MAX_FILE_BYTES bytes."
            echo "> Actual: $size bytes."
            echo ">"
            echo "> File path is preserved so it can be requested separately."
            echo
        } >> "$output"

        return 0
    fi

    {
        echo "\`\`\`$language"
        cat "$file"
        echo
        echo "\`\`\`"
        echo
    } >> "$output"
}


# ============================================================
# Safely export Django/Python configuration
#
# Potentially sensitive assignment values are replaced with
# <REDACTED>.
#
# Examples:
#
# SECRET_KEY = "..."
# DATABASE_PASSWORD = "..."
# AWS_SECRET_ACCESS_KEY = "..."
# API_TOKEN = "..."
#
# become:
#
# SECRET_KEY = "<REDACTED>"
# ============================================================

append_redacted_python_file() {
    local output="$1"
    local file="$2"

    [[ -f "$file" ]] || return 0

    local relative
    relative="$(relative_path "$file")"

    local size
    size="$(file_size_bytes "$file")"

    {
        echo
        echo "----------------------------------------------------------------"
        echo "FILE: $relative"
        echo "SIZE: $size bytes"
        echo "NOTE: Potential secret assignments are automatically redacted."
        echo "----------------------------------------------------------------"
        echo
    } >> "$output"

    if (( size > MAX_FILE_BYTES )); then
        {
            echo "> FILE OMITTED FROM FULL SNAPSHOT"
            echo ">"
            echo "> Reason: configuration file exceeds snapshot limit."
            echo "> Limit: $MAX_FILE_BYTES bytes."
            echo "> Actual: $size bytes."
            echo
        } >> "$output"

        return 0
    fi

    echo '```python' >> "$output"

    python3 - "$file" >> "$output" <<'PY'
import re
import sys
from pathlib import Path


path = Path(sys.argv[1])


SENSITIVE_NAME = re.compile(
    r"""
    ^
    \s*
    (?P<name>
        [A-Za-z_][A-Za-z0-9_]*
        (?:
            SECRET
            |
            PASSWORD
            |
            PASSWD
            |
            TOKEN
            |
            API_KEY
            |
            APIKEY
            |
            PRIVATE_KEY
            |
            ACCESS_KEY
            |
            SECRET_KEY
            |
            CLIENT_SECRET
            |
            SIGNING_KEY
            |
            AUTH_KEY
            |
            CREDENTIAL
            |
            CREDENTIALS
            |
            CERTIFICATE_PASSWORD
            |
            DB_PASSWORD
            |
            DATABASE_PASSWORD
        )
        [A-Za-z0-9_]*
    )
    \s*
    =
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def redact_line(line: str) -> str:
    stripped_newline = line.rstrip("\n")

    match = SENSITIVE_NAME.match(stripped_newline)

    if not match:
        return stripped_newline

    # Preserve indentation and variable name.
    prefix = stripped_newline[: match.end()]

    return f'{prefix} "<REDACTED>"'


try:
    content = path.read_text(
        encoding="utf-8",
        errors="replace",
    )
except Exception as exc:
    print(f"# Unable to read file: {exc}")
    raise SystemExit(0)


for line in content.splitlines():
    print(redact_line(line))
PY

    {
        echo '```'
        echo
    } >> "$output"
}


# ============================================================
# Standard snapshot header
# ============================================================

write_standard_header() {
    local output="$1"
    local title="$2"
    local description="$3"

    cat > "$output" <<EOF
# $title

Generated: $(date '+%Y-%m-%d %H:%M:%S')
Repository root: $ROOT_DIR

$description

This snapshot is generated automatically from the current repository state.

Security rules:
- Actual .env files are NEVER included.
- Potentially sensitive Python configuration assignments are redacted.
- Virtual environments are excluded.
- Generated/cache/build directories are excluded.
- Large individual files may be represented by path only.
EOF
}


# ============================================================
# Git snapshot
# ============================================================

append_git_snapshot() {
    local output="$1"

    separator "$output" "GIT SNAPSHOT"

    {
        echo '```text'

        if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

            echo "Repository root:"
            git -C "$ROOT_DIR" rev-parse --show-toplevel 2>/dev/null || true

            echo
            echo "Branch:"
            git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true

            echo
            echo "Commit:"
            git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || true

            echo
            echo "Working tree:"
            git -C "$ROOT_DIR" status --short 2>/dev/null || true

        else

            echo "Not a Git repository."

        fi

        echo '```'
    } >> "$output"
}


# ============================================================
# Common backend path exclusion helper
# ============================================================

is_excluded_backend_path() {
    local path="$1"

    case "$path" in
        */.git/*|\
        */.venv/*|\
        */venv/*|\
        */env/*|\
        */__pycache__/*|\
        */.pytest_cache/*|\
        */.mypy_cache/*|\
        */.ruff_cache/*|\
        */node_modules/*|\
        */staticfiles/*|\
        */media/*|\
        */chatgpt_sources/*)
            return 0
            ;;

        *)
            return 1
            ;;
    esac
}