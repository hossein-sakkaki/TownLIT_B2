#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/01_backend_core_domain_models.md"
TMP_FILE="$(mktemp)"

trap 'rm -f "$TMP_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Core Domain Models Snapshot" \
    "Authoritative Django model source for foundational identity, users, profiles, membership, organizations, relationships and other cross-feature domain entities."

append_git_snapshot "$OUTPUT_FILE"

# ============================================================
# Find important model source files.
#
# Strategy:
# 1. model modules living in foundational app paths
# 2. model modules containing known foundational class concepts
#
# This does NOT depend on one fixed TownLIT directory layout.
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/migrations/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
    \) -prune \
    -o -type f -name "*.py" -print \
    | while IFS= read -r file
do
    relative="${file#$ROOT_DIR/}"

    case "$relative" in
        *accounts*/models.py|\
        *accounts*/models/*.py|\
        *users*/models.py|\
        *users*/models/*.py|\
        *profiles*/models.py|\
        *profiles*/models/*.py|\
        *organizations*/models.py|\
        *organizations*/models/*.py|\
        *organisation*/models.py|\
        *organisation*/models/*.py|\
        *membership*/models.py|\
        *membership*/models/*.py|\
        *friendship*/models.py|\
        *friendship*/models/*.py|\
        *network*/models.py|\
        *network*/models/*.py|\
        *identity*/models.py|\
        *identity*/models/*.py)
            echo "$file" >> "$TMP_FILE"
            continue
            ;;
    esac

    if [[ "$(basename "$file")" == "models.py" ]] || [[ "$relative" == *"/models/"* ]]; then
        if grep -Eiq \
            'class[[:space:]]+(CustomUser|GuestUser|Guest|Member|Organization|Organisation|Friendship|UserDevice|UserDeviceKey|Profile|Founder|BoardMember|Membership|SocialConnection|LITCovenant|Boundary)[[:space:](:]' \
            "$file"
        then
            echo "$file" >> "$TMP_FILE"
        fi
    fi
done

sort -u "$TMP_FILE" -o "$TMP_FILE"

# ============================================================
# Inventory
# ============================================================

separator "$OUTPUT_FILE" "CORE MODEL FILE INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        echo "${file#$ROOT_DIR/}"
    done < "$TMP_FILE"

    echo '```'
} >> "$OUTPUT_FILE"

# ============================================================
# Full source
# ============================================================

separator "$OUTPUT_FILE" "CORE DOMAIN MODEL SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file" "python"
done < "$TMP_FILE"

# ============================================================
# AUTH_USER_MODEL references
# ============================================================

separator "$OUTPUT_FILE" "AUTH USER MODEL REFERENCES"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path '*/.venv/*' \
            -o -path '*/venv/*' \
            -o -path '*/migrations/*' \
            -o -path '*/__pycache__/*' \
        \) -prune \
        -o -type f -name "*.py" -print \
        | while IFS= read -r file
    do
        if grep -Eq \
            'AUTH_USER_MODEL|get_user_model|CustomUser' \
            "$file"
        then
            relative="${file#$ROOT_DIR/}"

            echo
            echo "FILE: $relative"

            grep -En \
                'AUTH_USER_MODEL|get_user_model|CustomUser' \
                "$file" \
                | head -n 30 \
                || true
        fi
    done

    echo
    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Core domain models snapshot created:"
echo "$OUTPUT_FILE"
echo