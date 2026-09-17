#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/02_backend_shared_infrastructure.md"
TMP_FILE="$(mktemp)"

trap 'rm -f "$TMP_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Shared Infrastructure Snapshot" \
    "Reusable backend infrastructure including authentication, permissions, middleware, base/abstract models, managers, validators, common API utilities, storage and shared policy infrastructure."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Discover reusable infrastructure files
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/migrations/*' \
        -o -path '*/tests/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
    \) -prune \
    -o -type f -name "*.py" -print \
    | while IFS= read -r file
do
    relative="${file#$ROOT_DIR/}"
    base="$(basename "$file")"

    case "$base" in
        permissions.py|\
        authentication.py|\
        middleware.py|\
        managers.py|\
        validators.py|\
        pagination.py|\
        throttling.py|\
        mixins.py|\
        exceptions.py)
            case "$relative" in
                *core/*|\
                *common/*|\
                *shared/*|\
                *accounts/*|\
                *security/*|\
                *main/*)
                    echo "$file" >> "$TMP_FILE"
                    ;;
            esac
            ;;
    esac

    if grep -Eiq \
        'class[[:space:]]+.*(BaseModel|TimeStampedModel|TimestampedModel|SoftDelete|BasePermission|Authentication|UserManager|AccountManager)' \
        "$file"
    then
        echo "$file" >> "$TMP_FILE"
    fi
done

sort -u "$TMP_FILE" -o "$TMP_FILE"

separator "$OUTPUT_FILE" "SHARED INFRASTRUCTURE INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$TMP_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SHARED INFRASTRUCTURE SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file" "python"
done < "$TMP_FILE"

# ============================================================
# DRF / JWT / Channels / Celery relevant settings snippets
# ============================================================

separator "$OUTPUT_FILE" "FRAMEWORK CONFIGURATION REFERENCES"

{
    echo '```text'

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
        | while IFS= read -r file
    do
        matches="$(
            grep -En \
                'REST_FRAMEWORK|SIMPLE_JWT|CHANNEL_LAYERS|CELERY_|AUTH_USER_MODEL|DEFAULT_AUTHENTICATION_CLASSES|DEFAULT_PERMISSION_CLASSES|CORS_|CSRF_|STORAGES|DEFAULT_FILE_STORAGE' \
                "$file" \
                2>/dev/null \
                || true
        )"

        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done

    echo
    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Shared backend infrastructure snapshot created:"
echo "$OUTPUT_FILE"
echo