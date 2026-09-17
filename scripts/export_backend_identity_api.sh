#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/03_backend_identity_api_contracts.md"

SOURCE_FILES_FILE="$(mktemp)"
URL_FILES_FILE="$(mktemp)"

trap 'rm -f "$SOURCE_FILES_FILE" "$URL_FILES_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Identity & Profile API Contracts" \
    "Backend API contracts for accounts, users, profiles, identity, membership and friendships. Organization APIs are intentionally excluded and exported separately by the Organizations snapshot."

append_git_snapshot "$OUTPUT_FILE"


# ============================================================
# Scope
#
# INCLUDED:
# - accounts
# - users
# - profiles
# - identity
# - membership / memberships
# - friendship / friendships
#
# EXCLUDED:
# - organizations / organisation / organisations
#
# Organization has its own authoritative snapshot:
# 04_backend_organizations.md
# ============================================================


# ============================================================
# Discover relevant API/domain files
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.git/*' \
        -o -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/env/*' \
        -o -path '*/migrations/*' \
        -o -path '*/tests/*' \
        -o -path '*/test/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
        -o -path '*/staticfiles/*' \
        -o -path '*/media/*' \
        -o -path '*/organizations/*' \
        -o -path '*/organization/*' \
        -o -path '*/organisations/*' \
        -o -path '*/organisation/*' \
    \) -prune \
    -o -type f -name "*.py" -print \
    | while IFS= read -r file
do
    relative="${file#$ROOT_DIR/}"
    base="$(basename "$file")"

    # --------------------------------------------------------
    # Hard organization exclusion.
    #
    # Keep this even though find already prunes those paths.
    # It protects us if the repository layout changes later.
    # --------------------------------------------------------

    if echo "$relative" | grep -Eiq \
        '(^|/)(organizations?|organisations?)(/|$)'
    then
        continue
    fi

    # --------------------------------------------------------
    # Only files belonging to identity/profile-related apps.
    # --------------------------------------------------------

    if ! echo "$relative" | grep -Eiq \
        '(^|/)(accounts?|users?|profiles?|identity|memberships?|friendships?)(/|$)'
    then
        continue
    fi

    # --------------------------------------------------------
    # Conventional Django / DRF files
    # --------------------------------------------------------

    case "$base" in
        serializers.py|\
        views.py|\
        viewsets.py|\
        urls.py|\
        permissions.py|\
        services.py|\
        selectors.py|\
        repositories.py|\
        managers.py|\
        validators.py|\
        filters.py|\
        pagination.py|\
        schemas.py|\
        signals.py|\
        constants.py)
            echo "$file" >> "$SOURCE_FILES_FILE"
            continue
            ;;
    esac

    # --------------------------------------------------------
    # Split-module layouts
    #
    # Examples:
    #
    # serializers/member.py
    # views/profile.py
    # api/profile.py
    # services/account.py
    # selectors/friendships.py
    # repositories/profile.py
    # permissions/profile.py
    # --------------------------------------------------------

    case "$relative" in
        */serializers/*.py|\
        */views/*.py|\
        */viewsets/*.py|\
        */api/*.py|\
        */services/*.py|\
        */selectors/*.py|\
        */repositories/*.py|\
        */permissions/*.py|\
        */filters/*.py|\
        */schemas/*.py)
            echo "$file" >> "$SOURCE_FILES_FILE"
            continue
            ;;
    esac

done


sort -u "$SOURCE_FILES_FILE" -o "$SOURCE_FILES_FILE"


# ============================================================
# API source inventory
# ============================================================

separator "$OUTPUT_FILE" "IDENTITY / PROFILE API FILE INVENTORY"

{
    echo '```text'

    if [[ ! -s "$SOURCE_FILES_FILE" ]]; then
        echo "No matching Identity/Profile API files were discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES_FILE"
    fi

    echo '```'
} >> "$OUTPUT_FILE"


# ============================================================
# Full API source
# ============================================================

separator "$OUTPUT_FILE" "IDENTITY / PROFILE API SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue

    append_file "$OUTPUT_FILE" "$file" "python"

done < "$SOURCE_FILES_FILE"


# ============================================================
# Relevant route files
#
# We also inspect project-level urls.py files because the root
# project router may include profile/account routes even though
# it lives outside the accounts/profile app.
#
# Organization routes are explicitly excluded.
# ============================================================

find "$ROOT_DIR" \
    \( \
        -path '*/.git/*' \
        -o -path '*/.venv/*' \
        -o -path '*/venv/*' \
        -o -path '*/env/*' \
        -o -path '*/migrations/*' \
        -o -path '*/tests/*' \
        -o -path '*/test/*' \
        -o -path '*/__pycache__/*' \
        -o -path '*/chatgpt_sources/*' \
        -o -path '*/organizations/*' \
        -o -path '*/organization/*' \
        -o -path '*/organisations/*' \
        -o -path '*/organisation/*' \
    \) -prune \
    -o -type f -name "urls.py" -print \
    | while IFS= read -r file
do
    relative="${file#$ROOT_DIR/}"

    if echo "$relative" | grep -Eiq \
        '(^|/)(organizations?|organisations?)(/|$)'
    then
        continue
    fi

    if grep -Eiq \
        'account|user|profile|member|guest|identity|friendship|friend|membership' \
        "$file"
    then
        echo "$file" >> "$URL_FILES_FILE"
    fi

done


sort -u "$URL_FILES_FILE" -o "$URL_FILES_FILE"


# ============================================================
# Route inventory
# ============================================================

separator "$OUTPUT_FILE" "IDENTITY / PROFILE ROUTE INVENTORY"

{
    echo '```text'

    if [[ ! -s "$URL_FILES_FILE" ]]; then
        echo "No matching route files were discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue

            echo
            echo "FILE: ${file#$ROOT_DIR/}"

            grep -Ein \
                'path\(|re_path\(|router\.register|include\(|account|user|profile|member|guest|identity|friendship|friend|membership' \
                "$file" \
                | grep -Eiv \
                    'organization|organisation' \
                || true

        done < "$URL_FILES_FILE"
    fi

    echo
    echo '```'
} >> "$OUTPUT_FILE"


# ============================================================
# Serializer / View / ViewSet class inventory
#
# This gives a compact architecture index before reading the
# complete source.
# ============================================================

separator "$OUTPUT_FILE" "API CLASS INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        matches="$(
            grep -En \
                '^[[:space:]]*class[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\(' \
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
# Endpoint/action inventory
#
# Useful for DRF ViewSets:
#
# @action(...)
# create()
# update()
# partial_update()
# retrieve()
# list()
# destroy()
# ============================================================

separator "$OUTPUT_FILE" "DRF ENDPOINT / ACTION INVENTORY"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        matches="$(
            grep -En \
                '@action|def[[:space:]]+(create|update|partial_update|retrieve|list|destroy|post|get|put|patch|delete)[[:space:]]*\(' \
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
# Important domain/API terminology index
# ============================================================

separator "$OUTPUT_FILE" "IDENTITY / PROFILE CONTRACT INDEX"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        matches="$(
            grep -Ein \
                'CustomUser|GuestUser|Member|Profile|ProfileMe|OwnerProfile|VisitorProfile|Friendship|friendship|Identity|verification|membership|current_user|currentUser|my-profile|my_profile|update-profile|update_profile|reactivate|deactivate' \
                "$file" \
                2>/dev/null \
                | grep -Eiv \
                    'organization|organisation' \
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
# Organization exclusion verification
#
# This is intentional: if this section reports anything,
# we know our scope filtering needs attention.
# ============================================================

separator "$OUTPUT_FILE" "ORGANIZATION EXCLUSION CHECK"

organization_hits="$(
    grep -Ein \
        'FILE: .*organizations?/|FILE: .*organisations?/' \
        "$OUTPUT_FILE" \
        2>/dev/null \
        || true
)"

{
    echo '```text'

    if [[ -z "$organization_hits" ]]; then
        echo "PASS"
        echo "No Organization app source files were included."
        echo
        echo "Organization backend source belongs in:"
        echo "04_backend_organizations.md"
    else
        echo "WARNING"
        echo "Unexpected Organization file references were found:"
        echo
        echo "$organization_hits"
    fi

    echo '```'
} >> "$OUTPUT_FILE"


echo
echo "✅ Identity / Profile API snapshot created:"
echo "$OUTPUT_FILE"
echo