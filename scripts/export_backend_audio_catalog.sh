#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/06_backend_audio_catalog.md"

APP_DIRS_FILE="$(mktemp)"
SOURCE_FILES_FILE="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$APP_DIRS_FILE" "$SOURCE_FILES_FILE" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Audio Catalog Feature Snapshot" \
    "Authoritative Audio Catalog backend including catalog models, taxonomy, media/conversion contracts, analytics, metrics, trending, admin tooling, serializers, API views, repositories/services, tasks, storage and operational support."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Locate Audio Catalog root
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.git/*' \
        -o -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/env/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
    \) -prune \
    -o -type d \
    \( \
        -name "audio_catalog" \
        -o -name "audiocatalog" \
        -o -name "audio-catalog" \
    \) \
    -print \
    | while IFS= read -r dir
do
    if [[ -f "$dir/apps.py" ]] \
        || [[ -f "$dir/models.py" ]] \
        || [[ -d "$dir/models" ]] \
        || [[ -d "$dir/admin" ]] \
        || [[ -d "$dir/tasks" ]]
    then
        echo "$dir"
    fi
done > "$APP_DIRS_FILE"

sort -u "$APP_DIRS_FILE" -o "$APP_DIRS_FILE"

# ============================================================
# Roots
# ============================================================

separator "$OUTPUT_FILE" "AUDIO CATALOG APP ROOTS"

{
    echo '```text'

    if [[ ! -s "$APP_DIRS_FILE" ]]; then
        echo "No Audio Catalog app root was discovered."
    else
        while IFS= read -r dir; do
            [[ -n "$dir" ]] || continue
            echo "${dir#$ROOT_DIR/}"
        done < "$APP_DIRS_FILE"
    fi

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Directory tree
# ============================================================

separator "$OUTPUT_FILE" "AUDIO CATALOG DIRECTORY TREE"

{
    echo '```text'

    while IFS= read -r app_dir; do
        [[ -n "$app_dir" ]] || continue

        echo
        echo "ROOT: ${app_dir#$ROOT_DIR/}"

        find "$app_dir" \
            \( \
                -path '*/__pycache__' \
                -o -path '*/migrations' \
                -o -path '*/tests' \
                -o -path '*/test' \
            \) -prune \
            -o -type d -print \
            | sed "s|$ROOT_DIR/||" \
            | sort

    done < "$APP_DIRS_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Source
# Includes admin/analytics.py, tasks, services, etc.
# ============================================================

while IFS= read -r app_dir; do
    [[ -n "$app_dir" ]] || continue

    find "$app_dir" \
        \( \
            -path '*/__pycache__/*' \
            -o -path '*/migrations/*' \
            -o -path '*/tests/*' \
            -o -path '*/test/*' \
        \) -prune \
        -o -type f \
        \( \
            -name "*.py" \
            -o -name "*.json" \
            -o -name "*.yaml" \
            -o -name "*.yml" \
            -o -name "*.md" \
        \) \
        -print

done < "$APP_DIRS_FILE" > "$SOURCE_FILES_FILE"

sort -u "$SOURCE_FILES_FILE" -o "$SOURCE_FILES_FILE"

separator "$OUTPUT_FILE" "AUDIO CATALOG SOURCE INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$SOURCE_FILES_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "AUDIO CATALOG SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES_FILE"

# ============================================================
# Architecture / behavior index
# ============================================================

separator "$OUTPUT_FILE" "AUDIO CATALOG FEATURE INDEX"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        matches="$(
            grep -Ein \
                'AudioTrack|AudioCategory|AudioCatalog|Metric|Trending|Analytics|playback|completion|skip|taxonomy|convert|conversion|codec|FFmpeg|Celery|shared_task|admin\.action|ModelAdmin|storage|S3' \
                "$file" \
                2>/dev/null \
                || true
        )"

        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi

    done < "$SOURCE_FILES_FILE"

    echo
    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Migration inventory
# ============================================================

while IFS= read -r app_dir; do
    [[ -n "$app_dir" ]] || continue

    find "$app_dir" \
        -type f \
        -path '*/migrations/*.py' \
        ! -name "__init__.py" \
        -print

done < "$APP_DIRS_FILE" > "$MIGRATIONS_FILE"

sort -u "$MIGRATIONS_FILE" -o "$MIGRATIONS_FILE"

separator "$OUTPUT_FILE" "AUDIO CATALOG MIGRATION INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$MIGRATIONS_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Audio Catalog snapshot created:"
echo "$OUTPUT_FILE"
echo