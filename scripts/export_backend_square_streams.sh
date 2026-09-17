#!/usr/bin/env bash

# scripts/export_backend_square_streams.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-15.
# Last Update by Hossein Sakkaki on 2026-09-15.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/08_backend_square_streams.md"

SQUARE_ROOT="$ROOT_DIR/apps/core/square"
STREAMS_ROOT="$ROOT_DIR/apps/core/streams"

SOURCE_FILES="$(mktemp)"
INTEGRATION_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$INTEGRATION_FILES" "$REFERENCE_FILES" "$MIGRATION_FILES"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Square & Streams Snapshot" \
    "Authoritative backend snapshot for Square/Explore and Streams, including complete owned source, routing/realtime integration, migration inventory, and focused cross-feature references."

append_git_snapshot "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SQUARE / STREAMS ROOTS"

{
    echo '```text'
    [[ -d "$SQUARE_ROOT" ]] && echo "apps/core/square" || echo "WARNING: apps/core/square was not found."
    [[ -d "$STREAMS_ROOT" ]] && echo "apps/core/streams" || echo "WARNING: apps/core/streams was not found."
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SQUARE / STREAMS DIRECTORY STRUCTURE"

{
    echo '```text'
    for dir in "$SQUARE_ROOT" "$STREAMS_ROOT"; do
        if [[ -d "$dir" ]]; then
            find "$dir" \
                \( -path '*/__pycache__' -o -path '*/migrations' -o -path '*/tests' -o -path '*/test' \) -prune \
                -o -type d -print \
                | sed "s|$ROOT_DIR/||" \
                | sort
        fi
    done
    echo '```'
} >> "$OUTPUT_FILE"

for dir in "$SQUARE_ROOT" "$STREAMS_ROOT"; do
    if [[ -d "$dir" ]]; then
        find "$dir" \
            \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' -o -path '*/test/*' \) -prune \
            -o -type f \
            \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.md" \) \
            -print >> "$SOURCE_FILES"
    fi
done

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"

separator "$OUTPUT_FILE" "SQUARE / STREAMS SOURCE INVENTORY"
{
    echo '```text'
    if [[ ! -s "$SOURCE_FILES" ]]; then
        echo "No Square/Streams source files were discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SQUARE SOURCE INVENTORY"
{
    echo '```text'
    if [[ -d "$SQUARE_ROOT" ]]; then
        find "$SQUARE_ROOT" \
            \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' -o -path '*/test/*' \) -prune \
            -o -type f \
            \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.md" \) \
            -print | sed "s|$ROOT_DIR/||" | sort
    else
        echo "No Square source discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "STREAMS SOURCE INVENTORY"
{
    echo '```text'
    if [[ -d "$STREAMS_ROOT" ]]; then
        find "$STREAMS_ROOT" \
            \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' -o -path '*/test/*' \) -prune \
            -o -type f \
            \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.md" \) \
            -print | sed "s|$ROOT_DIR/||" | sort
    else
        echo "No Streams source discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SQUARE / STREAMS CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ -n "$file" && "$file" == *.py ]] || continue
        matches="$(
            grep -En \
                '^[[:space:]]*class[[:space:]]+[A-Za-z_][A-Za-z0-9_]*|^[[:space:]]*def[[:space:]]+[A-Za-z_][A-Za-z0-9_]*|^[[:space:]]*async[[:space:]]+def[[:space:]]+[A-Za-z_][A-Za-z0-9_]*|Square|Explore|Stream|Feed|Cursor|Ranking|Realtime|WebSocket' \
                "$file" 2>/dev/null | head -n 220 || true
        )"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

for dir in "$ROOT_DIR/config" "$ROOT_DIR/townlit" "$ROOT_DIR/apps/core"; do
    [[ -d "$dir" ]] || continue
    find "$dir" \
        \( -path "$SQUARE_ROOT/*" -o -path "$STREAMS_ROOT/*" -o -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' \) -prune \
        -o -type f -name "*.py" -print \
        | while IFS= read -r file; do
            if grep -Eiq 'apps\.core\.(square|streams)|core\.(square|streams)|Square|Explore|Stream|Streams' "$file"; then
                echo "$file" >> "$INTEGRATION_FILES"
            fi
        done
done

sort -u "$INTEGRATION_FILES" -o "$INTEGRATION_FILES"

separator "$OUTPUT_FILE" "SQUARE / STREAMS INTEGRATION SOURCE"
if [[ ! -s "$INTEGRATION_FILES" ]]; then
    {
        echo '```text'
        echo "No direct Square/Streams integration source discovered."
        echo '```'
    } >> "$OUTPUT_FILE"
else
    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        append_file "$OUTPUT_FILE" "$file"
    done < "$INTEGRATION_FILES"
fi

find "$ROOT_DIR" \
    \( -path "$ROOT_DIR/.git/*" -o -path "$ROOT_DIR/.venv/*" -o -path "$ROOT_DIR/venv/*" -o -path "$ROOT_DIR/env/*" \
       -o -path "$ROOT_DIR/chatgpt_sources/*" -o -path "$SQUARE_ROOT/*" -o -path "$STREAMS_ROOT/*" \
       -o -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' \) -prune \
    -o -type f -name "*.py" -print \
    | while IFS= read -r file; do
        if grep -Eiq 'apps\.core\.(square|streams)|core\.(square|streams)|Square|Explore|Stream' "$file"; then
            if ! grep -Fxq "$file" "$INTEGRATION_FILES" 2>/dev/null; then
                echo "$file" >> "$REFERENCE_FILES"
            fi
        fi
    done

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "$OUTPUT_FILE" "CROSS-FEATURE SQUARE / STREAMS REFERENCES"
{
    echo '```text'
    if [[ ! -s "$REFERENCE_FILES" ]]; then
        echo "No additional cross-feature Square/Streams references discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            matches="$(
                grep -Ein 'apps\.core\.(square|streams)|core\.(square|streams)|Square|Explore|Stream' "$file" \
                    2>/dev/null | head -n 80 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

for dir in "$SQUARE_ROOT" "$STREAMS_ROOT"; do
    if [[ -d "$dir/migrations" ]]; then
        find "$dir/migrations" -type f -name "*.py" ! -name "__init__.py" -print >> "$MIGRATION_FILES"
    fi
done

sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "$OUTPUT_FILE" "SQUARE / STREAMS MIGRATION INVENTORY"
{
    echo '```text'
    if [[ ! -s "$MIGRATION_FILES" ]]; then
        echo "No Square/Streams migrations discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATION_FILES"
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SQUARE / STREAMS SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Square / Streams snapshot created:"
echo "$OUTPUT_FILE"
echo
