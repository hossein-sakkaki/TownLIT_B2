#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/05_backend_conversation.md"

APP_DIRS_FILE="$(mktemp)"
SOURCE_FILES_FILE="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$APP_DIRS_FILE" "$SOURCE_FILES_FILE" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Conversation Feature Snapshot" \
    "Authoritative conversation/messenger backend including models, serializers, API views, services, selectors, encryption-related contracts, websocket consumers/handlers, routing, delivery/read logic, reactions, pins, forwarding, replies, attachments, notifications and background tasks."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Discover actual Conversation app
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
        -name "conversation" \
        -o -name "conversations" \
        -o -name "messenger" \
        -o -name "messaging" \
    \) \
    -print \
    | while IFS= read -r dir
do
    if [[ -f "$dir/apps.py" ]] \
        || [[ -f "$dir/models.py" ]] \
        || [[ -d "$dir/models" ]] \
        || [[ -f "$dir/consumers.py" ]] \
        || [[ -f "$dir/routing.py" ]]
    then
        echo "$dir"
    fi
done > "$APP_DIRS_FILE"

sort -u "$APP_DIRS_FILE" -o "$APP_DIRS_FILE"

# ============================================================
# Roots
# ============================================================

separator "$OUTPUT_FILE" "CONVERSATION APP ROOTS"

{
    echo '```text'

    if [[ ! -s "$APP_DIRS_FILE" ]]; then
        echo "No Conversation app root was discovered."
    else
        while IFS= read -r dir; do
            [[ -n "$dir" ]] || continue
            echo "${dir#$ROOT_DIR/}"
        done < "$APP_DIRS_FILE"
    fi

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Tree
# ============================================================

separator "$OUTPUT_FILE" "CONVERSATION DIRECTORY TREE"

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

separator "$OUTPUT_FILE" "CONVERSATION SOURCE INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$SOURCE_FILES_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "CONVERSATION SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES_FILE"

# ============================================================
# WebSocket / Channels architecture summary
# ============================================================

separator "$OUTPUT_FILE" "CONVERSATION REALTIME / CHANNELS REFERENCES"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        matches="$(
            grep -Ein \
                'AsyncJsonWebsocketConsumer|AsyncWebsocketConsumer|WebsocketConsumer|group_send|group_add|group_discard|channel_layer|websocket|consumer|dialogue|message_(sent|delivered|read)|typing|recording|reaction|pin|reply|forward' \
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
# External ASGI / central websocket references
# ============================================================

separator "$OUTPUT_FILE" "PROJECT-LEVEL CONVERSATION REALTIME WIRING"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path '*/.venv/*' \
            -o -path '*/venv/*' \
            -o -path '*/migrations/*' \
            -o -path '*/__pycache__/*' \
        \) -prune \
        -o -type f \
        \( \
            -name "asgi.py" \
            -o -name "routing.py" \
            -o -name "*consumer*.py" \
            -o -name "*handler*.py" \
        \) \
        -print \
        | while IFS= read -r file
    do
        matches="$(
            grep -Ein \
                'conversation|dialogue|message|messenger' \
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

separator "$OUTPUT_FILE" "CONVERSATION MIGRATION INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$MIGRATIONS_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Conversation snapshot created:"
echo "$OUTPUT_FILE"
echo