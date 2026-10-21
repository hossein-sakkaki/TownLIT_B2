#!/usr/bin/env bash

# scripts/export_backend_validators.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-18.
# Last Update by Hossein Sakkaki on 2026-10-18.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ROOT_DIR="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null)"; then
    :
else
    ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"
OUTPUT_FILE="$OUTPUT_DIR/12_backend_validators.md"

mkdir -p "$OUTPUT_DIR"

VALIDATOR_DIRS="$(mktemp)"
SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"

trap 'rm -f "$VALIDATOR_DIRS" "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATION_FILES"' EXIT

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

cat > "$OUTPUT_FILE" <<'EOF'
# TownLIT Backend — Validators Snapshot

**Purpose:** Complete Backend validators snapshot. It captures every `validators/` directory recursively, standalone validator/validation source files, validation contracts, and cross-feature validator usages.

**Security rule:** Environment files, secrets, keys, media and generated artifacts are excluded.

**Migration rule:** Migration files are inventoried but not embedded as canonical current-state implementation.
EOF

{
    echo
    echo '```text'
    echo "Repository: $ROOT_DIR"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %z')"
    if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "Branch: $(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
        echo "Commit: $(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
    fi
    echo '```'
} >> "$OUTPUT_FILE"

for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue
    find "$base" -type d -iname validators -print 2>/dev/null >> "$VALIDATOR_DIRS"
done

sort -u "$VALIDATOR_DIRS" -o "$VALIDATOR_DIRS"

separator "VALIDATOR DIRECTORIES"
{
    echo '```text'
    if [[ -s "$VALIDATOR_DIRS" ]]; then
        while IFS= read -r dir; do
            is_ignored_path "$dir/" && continue
            echo "${dir#$ROOT_DIR/}"
        done < "$VALIDATOR_DIRS"
    else
        echo "No validators directories were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

while IFS= read -r dir; do
    [[ -d "$dir" ]] || continue
    is_ignored_path "$dir/" && continue

    while IFS= read -r file; do
        is_ignored_path "$file" && continue
        is_supported_source "$file" || continue

        if [[ "$file" == */migrations/* ]]; then
            echo "$file" >> "$MIGRATION_FILES"
        else
            echo "$file" >> "$SOURCE_FILES"
        fi
    done < <(find "$dir" -type f -print 2>/dev/null)
done < "$VALIDATOR_DIRS"

for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue

    while IFS= read -r file; do
        is_ignored_path "$file" && continue
        is_supported_source "$file" || continue

        if [[ "$file" == */migrations/* ]]; then
            echo "$file" >> "$MIGRATION_FILES"
        else
            echo "$file" >> "$SOURCE_FILES"
        fi
    done < <(
        find "$base" -type f \
            \( -iname 'validators.py' -o -iname '*validator*.py' -o -iname '*validation*.py' \) \
            -print 2>/dev/null
    )
done

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "VALIDATOR SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    else
        echo "No validator source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "VALIDATOR CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -En \
                '^[[:space:]]*(class|def|async[[:space:]]+def)[[:space:]]+[A-Za-z0-9_]*(Validator|Validation|Validate)[A-Za-z0-9_]*|ValidationError|validate_|validator' \
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

for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue

    while IFS= read -r file; do
        is_ignored_path "$file" && continue
        [[ "$file" == *.py ]] || continue
        [[ "$file" == */migrations/* ]] && continue

        if grep -Eiq \
            'from .*validators import|import .*validators|ValidationError|validate_[A-Za-z0-9_]+|[A-Za-z0-9_]+Validator' \
            "$file"
        then
            if ! grep -Fxq "$file" "$SOURCE_FILES" 2>/dev/null; then
                echo "$file" >> "$REFERENCE_FILES"
            fi
        fi
    done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "CROSS-FEATURE VALIDATOR REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(
                grep -En \
                    'from .*validators import|import .*validators|ValidationError|validate_[A-Za-z0-9_]+|[A-Za-z0-9_]+Validator' \
                    "$file" 2>/dev/null | head -n 140 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional validator references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "VALIDATOR MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATION_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATION_FILES"
    else
        echo "No validator-related migration files discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "VALIDATOR COMPLETE SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Validators snapshot created:"
echo "$OUTPUT_FILE"
echo
