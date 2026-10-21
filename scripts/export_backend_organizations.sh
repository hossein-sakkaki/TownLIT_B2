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
    "Authoritative Organizations backend snapshot including the main organizations app, nested organization modules such as church and worship, apps/organization_content, apps/organization_media, apps/media_conversion, models, serializers, APIs, views, permissions, services, selectors, tasks, admin, signals, routing, content-safety/media-conversion integrations, and supporting domain logic."

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

# Explicit organization-domain apps that are part of the same feature package.
for dir in \
    "$ROOT_DIR/apps/organization_content" \
    "$ROOT_DIR/apps/organization_media" \
    "$ROOT_DIR/apps/media_conversion"
do
    if [[ -d "$dir" ]]; then
        echo "$dir" >> "$APP_DIRS_FILE"
    fi
done

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
# Required companion-app status
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATION CONTENT / MEDIA / CONVERSION ROOT STATUS"

{
    echo '```text'

    for rel in \
        "apps/organization_content" \
        "apps/organization_media" \
        "apps/media_conversion"
    do
        if [[ -d "$ROOT_DIR/$rel" ]]; then
            echo "FOUND: $rel"
        else
            echo "WARNING: $rel was not found."
        fi
    done

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Directory tree
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

    found=0

    while IFS= read -r app_dir; do
        [[ -n "$app_dir" ]] || continue

        if [[ -d "$app_dir/modules" ]]; then
            find "$app_dir/modules" \
                -mindepth 1 \
                -maxdepth 2 \
                -type d \
                ! -name "__pycache__" \
                ! -name "migrations" \
                | sed "s|$ROOT_DIR/||" \
                | sort
            found=1
        fi
    done < "$APP_DIRS_FILE"

    [[ "$found" -eq 1 ]] || echo "No nested Organization modules directory was discovered."

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Collect actual source files recursively
#
# This includes the entire source surface under:
# - main Organizations app
# - nested church/worship/future modules
# - apps/organization_content
# - apps/organization_media
# - apps/media_conversion
#
# Migrations are inventoried separately.
# ============================================================

while IFS= read -r app_dir; do
    [[ -n "$app_dir" ]] || continue

    find "$app_dir" \
        \( \
            -path '*/__pycache__/*' \
            -o -path '*/migrations/*' \
        \) -prune \
        -o -type f \
        \( \
            -name "*.py" \
            -o -name "*.json" \
            -o -name "*.yaml" \
            -o -name "*.yml" \
            -o -name "*.toml" \
            -o -name "*.md" \
            -o -name "*.txt" \
        \) \
        -print

done < "$APP_DIRS_FILE" > "$SOURCE_FILES_FILE"

sort -u "$SOURCE_FILES_FILE" -o "$SOURCE_FILES_FILE"

separator "$OUTPUT_FILE" "ORGANIZATIONS SOURCE INVENTORY"

{
    echo '```text'

    if [[ ! -s "$SOURCE_FILES_FILE" ]]; then
        echo "No Organization source files were discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES_FILE"
    fi

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Dedicated source indexes
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATION CONTENT SOURCE INDEX"
{
    echo '```text'
    if [[ -d "$ROOT_DIR/apps/organization_content" ]]; then
        grep -F "$ROOT_DIR/apps/organization_content/" "$SOURCE_FILES_FILE" 2>/dev/null \
            | sed "s|$ROOT_DIR/||" || true
    else
        echo "apps/organization_content was not found."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ORGANIZATION MEDIA SOURCE INDEX"
{
    echo '```text'
    if [[ -d "$ROOT_DIR/apps/organization_media" ]]; then
        grep -F "$ROOT_DIR/apps/organization_media/" "$SOURCE_FILES_FILE" 2>/dev/null \
            | sed "s|$ROOT_DIR/||" || true
    else
        echo "apps/organization_media was not found."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "MEDIA CONVERSION SOURCE INDEX"
{
    echo '```text'
    if [[ -d "$ROOT_DIR/apps/media_conversion" ]]; then
        grep -F "$ROOT_DIR/apps/media_conversion/" "$SOURCE_FILES_FILE" 2>/dev/null \
            | sed "s|$ROOT_DIR/||" || true
    else
        echo "apps/media_conversion was not found."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Content Safety / moderation integration references inside the
# organization content/media/conversion domain
# ============================================================

separator "$OUTPUT_FILE" "CONTENT SAFETY / MODERATION INTEGRATION REFERENCES"

{
    echo '```text'

    for dir in \
        "$ROOT_DIR/apps/organization_content" \
        "$ROOT_DIR/apps/organization_media" \
        "$ROOT_DIR/apps/media_conversion"
    do
        [[ -d "$dir" ]] || continue

        find "$dir" -type f -name "*.py" -print \
            | while IFS= read -r file; do
                matches="$(
                    grep -Ein \
                        'content_safety|ContentSafety|moderation|safety|validator|validation' \
                        "$file" \
                        2>/dev/null \
                        | head -n 120 \
                        || true
                )"

                if [[ -n "$matches" ]]; then
                    echo
                    echo "FILE: ${file#$ROOT_DIR/}"
                    echo "$matches"
                fi
            done
    done

    echo
    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Media conversion / processing integration index
# ============================================================

separator "$OUTPUT_FILE" "MEDIA CONVERSION / PROCESSING INTEGRATION INDEX"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" && "$file" == *.py ]] || continue

        matches="$(
            grep -Ein \
                'media_conversion|MediaConversion|convert|conversion|transcode|transcoding|thumbnail|ffmpeg|ffprobe|processing|processed|variant|rendition' \
                "$file" \
                2>/dev/null \
                | head -n 140 \
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

    if [[ ! -s "$MIGRATIONS_FILE" ]]; then
        echo "No Organization-related migrations were discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATIONS_FILE"
    fi

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Organization route references outside the apps
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
            -o -path '*/chatgpt_sources/*' \
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
                'organization|organisation|church|worship|organization_content|organization_media|media_conversion' \
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
