#!/usr/bin/env bash

# scripts/export_backend_conversation_complete.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-02.
# Last Update by Hossein Sakkaki on 2026-10-02.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"
OUTPUT_FILE="$OUTPUT_DIR/05_backend_conversation.md"

mkdir -p "$OUTPUT_DIR"

OWNED_ROOTS="$(mktemp)"
SOURCE_FILES="$(mktemp)"
INTEGRATION_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"
FILTERED_ROOTS="$(mktemp)"

trap 'rm -f "$OWNED_ROOTS" "$SOURCE_FILES" "$INTEGRATION_FILES" "$REFERENCE_FILES" "$MIGRATION_FILES" "$FILTERED_ROOTS"' EXIT

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

is_ignored_path() {
    local path="$1"
    [[ "$path" == *"/.git/"* ]] && return 0
    [[ "$path" == *"/.venv/"* ]] && return 0
    [[ "$path" == *"/venv/"* ]] && return 0
    [[ "$path" == *"/node_modules/"* ]] && return 0
    [[ "$path" == *"/__pycache__/"* ]] && return 0
    [[ "$path" == *"/.pytest_cache/"* ]] && return 0
    [[ "$path" == *"/chatgpt_sources/"* ]] && return 0
    [[ "$path" == *"/staticfiles/"* ]] && return 0
    [[ "$path" == *"/media/"* ]] && return 0
    [[ "$path" == *"/.env"* ]] && return 0
    [[ "$path" == *"/secrets/"* ]] && return 0
    [[ "$path" == *"/private_keys/"* ]] && return 0
    return 1
}

is_supported_source() {
    case "$1" in
        *.py|*.sh|*.json|*.yml|*.yaml|*.toml|*.md|*.txt) return 0 ;;
        *) return 1 ;;
    esac
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

is_owned_root_name() {
    local name
    name="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    case "$name" in
        conversation|conversations|messaging|messenger) return 0 ;;
        *) return 1 ;;
    esac
}

is_in_owned_root() {
    local file="$1"
    local root
    while IFS= read -r root; do
        [[ -n "$root" ]] || continue
        if [[ "$file" == "$root" || "$file" == "$root"/* ]]; then
            return 0
        fi
    done < "$OWNED_ROOTS"
    return 1
}

cat > "$OUTPUT_FILE" <<'HEADER'
# TownLIT Backend — Conversation Snapshot

**Purpose:** Authoritative Backend snapshot for TownLIT Conversation / Messaging. It captures complete owned source plus API, serializers, permissions, selectors/services, realtime/WebSocket, message delivery, participants, read state, typing, reactions, attachments/media references, notifications, moderation/safety integration, tasks, and cross-feature references.

**Migration rule:** Migration files are inventoried but not embedded as canonical current-state implementation.

HEADER

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

# Discover owned Conversation / Messaging roots.
while IFS= read -r dir; do
    is_ignored_path "$dir/" && continue
    is_owned_root_name "$(basename "$dir")" || continue
    rel="${dir#$ROOT_DIR/}"
    case "$rel" in
        apps/*|townlit/*) echo "$dir" >> "$OWNED_ROOTS" ;;
    esac
done < <(find "$ROOT_DIR/apps" "$ROOT_DIR/townlit" -type d -print 2>/dev/null | sort)

sort -u "$OWNED_ROOTS" -o "$OWNED_ROOTS"

# Keep highest matching roots only.
while IFS= read -r candidate; do
    [[ -n "$candidate" ]] || continue
    nested=0
    while IFS= read -r existing; do
        [[ -n "$existing" ]] || continue
        if [[ "$candidate" == "$existing"/* ]]; then
            nested=1
            break
        fi
    done < "$FILTERED_ROOTS"
    [[ "$nested" -eq 1 ]] || echo "$candidate" >> "$FILTERED_ROOTS"
done < "$OWNED_ROOTS"
mv "$FILTERED_ROOTS" "$OWNED_ROOTS"

separator "CONVERSATION OWNED ROOTS"
{
    echo '```text'
    if [[ -s "$OWNED_ROOTS" ]]; then
        while IFS= read -r dir; do echo "${dir#$ROOT_DIR/}"; done < "$OWNED_ROOTS"
    else
        echo "No directory named Conversation/Conversations/Messaging/Messenger was discovered."
        echo "Keyword and filename discovery will still collect Conversation implementation references."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

# Complete source under owned roots.
while IFS= read -r dir; do
    [[ -d "$dir" ]] || continue
    while IFS= read -r file; do
        is_ignored_path "$file" && continue
        is_supported_source "$file" || continue
        if [[ "$file" == */migrations/* ]]; then
            echo "$file" >> "$MIGRATION_FILES"
        else
            echo "$file" >> "$SOURCE_FILES"
        fi
    done < <(find "$dir" -type f -print 2>/dev/null)
done < "$OWNED_ROOTS"

# Conversation-named files outside owned roots.
while IFS= read -r file; do
    is_ignored_path "$file" && continue
    is_supported_source "$file" || continue
    if [[ "$file" == */migrations/* ]]; then
        echo "$file" >> "$MIGRATION_FILES"
    else
        echo "$file" >> "$SOURCE_FILES"
    fi
done < <(find "$ROOT_DIR/apps" "$ROOT_DIR/townlit" -type f \( -iname '*conversation*.py' -o -iname '*messaging*.py' -o -iname '*messenger*.py' -o -iname '*conversation*.md' -o -iname '*messaging*.md' -o -iname '*messenger*.md' \) -print 2>/dev/null)

INTEGRATION_BASENAMES_REGEX='^(urls|routing|consumers|admin|apps|tasks|signals|services|selectors|permissions|serializers|views|api|events|handlers|notifications|push|websocket|pagination|filters|throttles|middleware)\.py$'
KEYWORDS_REGEX='Conversation|conversation|Messaging|messaging|Messenger|messenger|ConversationMessage|DirectMessage|MessageThread|message_thread|read_receipt|ReadReceipt|typing|Typing|reaction|Reaction'

# Architecture-level integration files outside owned roots.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        is_ignored_path "$file" && continue
        [[ "$file" == *.py ]] || continue
        [[ "$file" == */migrations/* ]] && continue
        is_in_owned_root "$file" && continue
        basename_file="$(basename "$file")"
        if [[ "$basename_file" =~ $INTEGRATION_BASENAMES_REGEX ]] && grep -Eiq "$KEYWORDS_REGEX" "$file"; then
            echo "$file" >> "$INTEGRATION_FILES"
        fi
    done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done

cat "$INTEGRATION_FILES" >> "$SOURCE_FILES"
sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "CONVERSATION SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$SOURCE_FILES"
    else
        echo "No Conversation source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(grep -En '^[[:space:]]*(class|def|async[[:space:]]+def)[[:space:]]+[A-Za-z0-9_]*(Conversation|Message|Thread|Participant|Member|Receipt|Reaction|Attachment|Typing|Inbox|Messenger|Chat)[A-Za-z0-9_]*|Conversation|conversation' "$file" 2>/dev/null | head -n 160 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION API / SERIALIZER / PERMISSION / PAGINATION INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        rel="${file#$ROOT_DIR/}"
        if echo "$rel" | grep -Eiq '/(urls|views|api|serializers|permissions|pagination|filters|throttles)\.py$'; then
            matches="$(grep -En "$KEYWORDS_REGEX" "$file" 2>/dev/null | head -n 120 || true)"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: $rel"
                echo "$matches"
            fi
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION REALTIME / WEBSOCKET / DELIVERY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        rel="${file#$ROOT_DIR/}"
        if echo "$rel" | grep -Eiq 'routing|consumer|websocket|event|handler|signal|service|task'; then
            matches="$(grep -Ein 'conversation|message|typing|receipt|read|reaction|participant|channel|group|websocket|event|delivery' "$file" 2>/dev/null | head -n 160 || true)"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: $rel"
                echo "$matches"
            fi
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION NOTIFICATION / PUSH INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        if grep -Eiq 'notification|push|apns|fcm|badge' "$file" && grep -Eiq "$KEYWORDS_REGEX" "$file"; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            grep -Ein 'conversation|message|notification|push|apns|fcm|badge' "$file" 2>/dev/null | head -n 120 || true
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION SAFETY / MODERATION / BLOCKING / PRIVACY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        if grep -Eiq 'block|blocked|moderation|report|safety|privacy|visibility|permission|sanctuary' "$file" && grep -Eiq 'conversation|message|participant|thread|messenger' "$file"; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            grep -Ein 'conversation|message|participant|block|blocked|moderation|report|safety|privacy|visibility|permission|sanctuary' "$file" 2>/dev/null | head -n 140 || true
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

# Cross-feature references as snippets only.
while IFS= read -r file; do
    is_ignored_path "$file" && continue
    [[ "$file" == *.py ]] || continue
    [[ "$file" == */migrations/* ]] && continue
    is_in_owned_root "$file" && continue
    if grep -Eiq "$KEYWORDS_REGEX" "$file" && ! grep -Fxq "$file" "$SOURCE_FILES" 2>/dev/null; then
        echo "$file" >> "$REFERENCE_FILES"
    fi
done < <(find "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config" -type f -name '*.py' -print 2>/dev/null)

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "CROSS-FEATURE CONVERSATION REFERENCES"
{
    echo '```text'
    if [[ ! -s "$REFERENCE_FILES" ]]; then
        echo "No additional cross-feature Conversation references discovered."
    else
        while IFS= read -r file; do
            matches="$(grep -En "$KEYWORDS_REGEX" "$file" 2>/dev/null | head -n 100 || true)"
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

separator "CONVERSATION MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATION_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$MIGRATION_FILES"
    else
        echo "No Conversation migration files discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "CONVERSATION COMPLETE SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Conversation snapshot created:"
echo "$OUTPUT_FILE"
echo
