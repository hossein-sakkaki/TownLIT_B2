#!/usr/bin/env bash

# scripts/export_backend_notifications.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"
OUTPUT_FILE="$OUTPUT_DIR/10_backend_notifications.md"

mkdir -p "$OUTPUT_DIR"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATION_FILES"' EXIT

separator() {
    local title="$1"
    {
        echo
        echo "---"
        echo
        echo "# $title"
        echo
    } >> "$OUTPUT_FILE"
}

append_file() {
    local file="$1"
    local rel="${file#$ROOT_DIR/}"
    local ext="${file##*.}"
    local lang="text"

    case "$ext" in
        py) lang="python" ;;
        sh) lang="bash" ;;
        json) lang="json" ;;
        yml|yaml) lang="yaml" ;;
        toml) lang="toml" ;;
        md) lang="markdown" ;;
        txt) lang="text" ;;
    esac

    {
        echo
        echo "## FILE: $rel"
        echo
        echo "\`\`\`$lang"
        cat "$file"
        echo
        echo "\`\`\`"
        echo
    } >> "$OUTPUT_FILE"
}

is_ignored() {
    local p="$1"
    [[ "$p" == *"/.git/"* ]] && return 0
    [[ "$p" == *"/.venv/"* ]] && return 0
    [[ "$p" == *"/venv/"* ]] && return 0
    [[ "$p" == *"/node_modules/"* ]] && return 0
    [[ "$p" == *"/__pycache__/"* ]] && return 0
    [[ "$p" == *"/.pytest_cache/"* ]] && return 0
    [[ "$p" == *"/chatgpt_sources/"* ]] && return 0
    [[ "$p" == *"/staticfiles/"* ]] && return 0
    [[ "$p" == *"/media/"* ]] && return 0
    [[ "$p" == *"/.env"* ]] && return 0
    return 1
}

KEYWORDS='Notification|notification|PushNotification|push_notification|push notification|APNS|apns|FCM|fcm|DeviceToken|device_token|PushToken|push_token|NotificationPreference|notification_preference|badge|unread'

cat > "$OUTPUT_FILE" <<'EOF'
# TownLIT Backend — Notifications Snapshot

**Purpose:** Authoritative Backend snapshot for notification domain/source, preferences, device/push tokens, APNs/FCM delivery, unread/badge state, tasks, API/serializers/permissions, realtime hooks, and cross-feature producers.

**Migration rule:** Migrations are inventoried, not embedded as canonical current-state source.

EOF

{
    echo '```text'
    echo "Repository: $ROOT_DIR"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %z')"
    if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "Branch: $(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
        echo "Commit: $(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
    fi
    echo '```'
} >> "$OUTPUT_FILE"

# Complete source from dedicated Notification roots.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r dir; do
        is_ignored "$dir/" && continue
        name="$(basename "$dir" | tr '[:upper:]' '[:lower:]')"
        case "$name" in
            notification|notifications|push_notification|push_notifications|pushnotifications)
                while IFS= read -r file; do
                    is_ignored "$file" && continue
                    case "$file" in
                        *.py|*.sh|*.json|*.yml|*.yaml|*.toml|*.md|*.txt)
                            if [[ "$file" == */migrations/* ]]; then
                                echo "$file" >> "$MIGRATION_FILES"
                            else
                                echo "$file" >> "$SOURCE_FILES"
                            fi
                            ;;
                    esac
                done < <(find "$dir" -type f -print 2>/dev/null)
                ;;
        esac
    done < <(find "$base" -type d -print 2>/dev/null)
done

# Named notification/push source anywhere.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        is_ignored "$file" && continue
        if [[ "$file" == */migrations/* ]]; then
            echo "$file" >> "$MIGRATION_FILES"
        else
            echo "$file" >> "$SOURCE_FILES"
        fi
    done < <(
        find "$base" -type f \
            \( -iname '*notification*.py' \
               -o -iname '*push*.py' \
               -o -iname '*apns*.py' \
               -o -iname '*fcm*.py' \
               -o -iname '*device_token*.py' \
               -o -iname '*push_token*.py' \) \
            -print 2>/dev/null
    )
done

# Architecture-level integration files.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        is_ignored "$file" && continue
        [[ "$file" == *.py ]] || continue
        [[ "$file" == */migrations/* ]] && continue
        case "$(basename "$file")" in
            urls.py|routing.py|consumers.py|admin.py|apps.py|tasks.py|signals.py|services.py|selectors.py|permissions.py|serializers.py|views.py|api.py|events.py|handlers.py|notifications.py|push.py|websocket.py|pagination.py|filters.py|throttles.py)
                if grep -Eiq "$KEYWORDS" "$file"; then
                    echo "$file" >> "$SOURCE_FILES"
                fi
                ;;
        esac
    done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "NOTIFICATION SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$SOURCE_FILES"
    else
        echo "No notification source discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "NOTIFICATION DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(grep -En 'Notification|notification|APNS|apns|FCM|fcm|DeviceToken|PushToken|badge|unread' "$file" 2>/dev/null | head -n 180 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "NOTIFICATION DELIVERY / TASKS / REALTIME INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        if grep -Eiq 'push|apns|fcm|delivery|retry|celery|task|websocket|channel|badge|unread' "$file"; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            grep -Ein 'notification|push|apns|fcm|delivery|retry|celery|task|websocket|channel|badge|unread' "$file" 2>/dev/null | head -n 180 || true
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

# Cross-feature producers/references as snippets.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        is_ignored "$file" && continue
        [[ "$file" == *.py ]] || continue
        [[ "$file" == */migrations/* ]] && continue
        if grep -Eiq "$KEYWORDS" "$file" && ! grep -Fxq "$file" "$SOURCE_FILES" 2>/dev/null; then
            echo "$file" >> "$REFERENCE_FILES"
        fi
    done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done
sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "CROSS-FEATURE NOTIFICATION PRODUCERS / REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(grep -En "$KEYWORDS" "$file" 2>/dev/null | head -n 120 || true)"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional cross-feature notification references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "NOTIFICATION MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATION_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$MIGRATION_FILES"
    else
        echo "No notification migration files discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "NOTIFICATION COMPLETE SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Notifications snapshot created:"
echo "$OUTPUT_FILE"
echo
