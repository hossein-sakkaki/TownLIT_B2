#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/04_backend_organizations.md"

APP_DIRS_FILE="$(mktemp)"
SOURCE_FILES_FILE="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$APP_DIRS_FILE" "$SOURCE_FILES_FILE" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Organizations Feature Snapshot" \
    "Authoritative Organizations backend snapshot including the root organizations app, nested organization modules such as church and worship, models, serializers, APIs, views, permissions, services, selectors, tasks, admin, signals, routing and supporting domain logic."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Locate the actual Organizations app roots
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.git/*' \
        -o -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/env/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
        -o -path '*/staticfiles/*' \
        -o -path '*/media/*' \
    \) -prune \
    -o -type d \
    \( \
        -name "organizations" \
        -o -name "organisation" \
        -o -name "organisations" \
    \) \
    -print \
    | while IFS= read -r dir
do
    if [[ -f "$dir/apps.py" ]] \
        || [[ -f "$dir/models.py" ]] \
        || [[ -d "$dir/models" ]] \
        || [[ -d "$dir/modules" ]]
    then
        echo "$dir"
    fi
done > "$APP_DIRS_FILE"

sort -u "$APP_DIRS_FILE" -o "$APP_DIRS_FILE"

# ============================================================
# Root inventory
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATIONS APP ROOTS"

{
    echo '```text'

    if [[ ! -s "$APP_DIRS_FILE" ]]; then
        echo "No Organizations app root was discovered."
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
# Critical for modules/church, modules/worship, etc.
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATIONS DIRECTORY TREE"

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
# Nested Organization module inventory
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATION MODULE INVENTORY"

{
    echo '```text'

    while IFS= read -r app_dir; do
        [[ -n "$app_dir" ]] || continue

        if [[ -d "$app_dir/modules" ]]; then
            find "$app_dir/modules" \
                -mindepth 1 \
                -maxdepth 2 \
                -type d \
                ! -name "__pycache__" \
                ! -name "migrations" \
                ! -name "tests" \
                | sed "s|$ROOT_DIR/||" \
                | sort
        fi

    done < "$APP_DIRS_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Collect actual source files recursively
#
# This intentionally includes everything under:
# apps/organizations/modules/church
# apps/organizations/modules/worship
# and future modules automatically.
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

separator "$OUTPUT_FILE" "ORGANIZATIONS SOURCE INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$SOURCE_FILES_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Full Organizations source
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATIONS SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES_FILE"

# ============================================================
# Migration inventory only
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

separator "$OUTPUT_FILE" "ORGANIZATIONS MIGRATION INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$MIGRATIONS_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Organization route references outside the app
# ============================================================

separator "$OUTPUT_FILE" "PROJECT-LEVEL ORGANIZATION ROUTING REFERENCES"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path '*/.git/*' \
            -o -path '*/.venv/*' \
            -o -path '*/venv/*' \
            -o -path '*/migrations/*' \
            -o -path '*/__pycache__/*' \
        \) -prune \
        -o -type f \
        \( \
            -name "urls.py" \
            -o -name "routing.py" \
            -o -name "asgi.py" \
        \) \
        -print \
        | while IFS= read -r file
    do
        matches="$(
            grep -Ein \
                'organization|organisation|church|worship' \
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
echo "✅ Organizations snapshot created:"
echo "$OUTPUT_FILE"
echo