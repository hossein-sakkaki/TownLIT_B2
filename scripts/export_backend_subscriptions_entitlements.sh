#!/usr/bin/env bash

# scripts/export_backend_subscriptions_entitlements.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-09-12.
# Last Update by Hossein Sakkaki on 2026-09-12.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/07_backend_subscriptions_entitlements.md"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"

trap '
    rm -f \
        "$SOURCE_FILES" \
        "$REFERENCE_FILES" \
        "$MIGRATION_FILES"
' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Subscriptions & Entitlements Snapshot" \
    "Authoritative backend snapshot for subscription accounts, plans, prices, trials, subscriptions, entitlements, grants, events, selectors, serializers, services, views, admin configuration, routing references, and Organization/payment integration."

append_git_snapshot "$OUTPUT_FILE"

SUBSCRIPTIONS_ROOT="$ROOT_DIR/apps/subscriptions"


# ============================================================
# Validate app
# ============================================================

separator "$OUTPUT_FILE" "SUBSCRIPTIONS APP ROOT"

{
    echo '```text'

    if [[ -d "$SUBSCRIPTIONS_ROOT" ]]; then
        echo "apps/subscriptions"
    else
        echo "WARNING: apps/subscriptions was not found."
    fi

    echo '```'
} >> "$OUTPUT_FILE"


# ============================================================
# Directory structure
# ============================================================

separator "$OUTPUT_FILE" "SUBSCRIPTIONS DIRECTORY STRUCTURE"

{
    echo '```text'

    if [[ -d "$SUBSCRIPTIONS_ROOT" ]]; then
        find "$SUBSCRIPTIONS_ROOT" \
            \( \
                -path '*/__pycache__' \
                -o -path '*/migrations' \
                -o -path '*/tests' \
                -o -path '*/test' \
            \) -prune \
            -o -type d -print \
            | sed "s|$ROOT_DIR/||" \
            | sort
    else
        echo "No subscriptions directory discovered."
    fi

    echo '```'
} >> "$OUTPUT_FILE"


# ============================================================
# Full subscription source
# ============================================================

if [[ -d "$SUBSCRIPTIONS_ROOT" ]]; then
    find "$SUBSCRIPTIONS_ROOT" \
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
        -print > "$SOURCE_FILES"
fi

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"


separator "$OUTPUT_FILE" "SUBSCRIPTIONS SOURCE INVENTORY"

{
    echo '```text'

    if [[ ! -s "$SOURCE_FILES" ]]; then
        echo "No subscription source files discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    fi

    echo '```'
} >> "$OUTPUT_FILE"


separator "$OUTPUT_FILE" "SUBSCRIPTIONS SOURCE"

while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"


# ============================================================
# Domain model index
# ============================================================

separator "$OUTPUT_FILE" "SUBSCRIPTION DOMAIN MODEL INDEX"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        [[ "$file" == *.py ]] || continue

        matches="$(
            grep -En \
                '^[[:space:]]*class[[:space:]]+(SubscriptionAccount|SubscriptionPlan|SubscriptionPlanPrice|Subscription|SubscriptionTrialUsage|EntitlementDefinition|PlanEntitlement|EntitlementGrant|SubscriptionEvent)\b' \
                "$file" \
                2>/dev/null \
                || true
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


# ============================================================
# Contract / business-rule index
# ============================================================

separator "$OUTPUT_FILE" "SUBSCRIPTION / ENTITLEMENT CONTRACT INDEX"

{
    echo '```text'

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        [[ "$file" == *.py ]] || continue

        matches="$(
            grep -Ein \
                'subscription|plan|price|trial|entitlement|grant|audience|billing|interval|cancel|expire|renew|active|current|module|service' \
                "$file" \
                2>/dev/null \
                | head -n 160 \
                || true
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


# ============================================================
# Project-level routes
# ============================================================

separator "$OUTPUT_FILE" "SUBSCRIPTION ROUTING REFERENCES"

{
    echo '```text'

    find "$ROOT_DIR" \
        \( \
            -path '*/.git/*' \
            -o -path '*/.venv/*' \
            -o -path '*/venv/*' \
            -o -path '*/env/*' \
            -o -path '*/migrations/*' \
            -o -path '*/__pycache__/*' \
            -o -path '*/chatgpt_sources/*' \
        \) -prune \
        -o -type f -name "urls.py" -print \
        | while IFS= read -r file
    do
        matches="$(
            grep -Ein \
                'subscription|subscriptions|entitlement|billing|plan' \
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
# Organization / payment integration references
#
# Full source stays in its own feature snapshots. Only relevant
# references are included here.
# ============================================================

for dir in \
    "$ROOT_DIR/apps/organizations" \
    "$ROOT_DIR/apps/payment"
do
    if [[ ! -d "$dir" ]]; then
        continue
    fi

    find "$dir" \
        \( \
            -path '*/__pycache__/*' \
            -o -path '*/migrations/*' \
            -o -path '*/tests/*' \
        \) -prune \
        -o -type f -name "*.py" -print \
        | while IFS= read -r file
    do
        if grep -Eiq \
            'subscription|entitlement|trial|plan|billing' \
            "$file"
        then
            echo "$file" >> "$REFERENCE_FILES"
        fi
    done
done

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"


separator "$OUTPUT_FILE" "ORGANIZATION / PAYMENT INTEGRATION REFERENCES"

{
    echo '```text'

    if [[ ! -s "$REFERENCE_FILES" ]]; then
        echo "No Organization/payment subscription references discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue

            matches="$(
                grep -Ein \
                    'subscription|entitlement|trial|plan|billing' \
                    "$file" \
                    2>/dev/null \
                    | head -n 100 \
                    || true
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


# ============================================================
# Migration inventory
# ============================================================

if [[ -d "$SUBSCRIPTIONS_ROOT/migrations" ]]; then
    find "$SUBSCRIPTIONS_ROOT/migrations" \
        -type f \
        -name "*.py" \
        ! -name "__init__.py" \
        -print > "$MIGRATION_FILES"
fi

sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"


separator "$OUTPUT_FILE" "SUBSCRIPTIONS MIGRATION INVENTORY"

{
    echo '```text'

    if [[ ! -s "$MIGRATION_FILES" ]]; then
        echo "No subscription migrations discovered."
    else
        while IFS= read -r file; do
            [[ -n "$file" ]] || continue
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATION_FILES"
    fi

    echo '```'
} >> "$OUTPUT_FILE"


echo
echo "✅ Backend Subscriptions / Entitlements snapshot created:"
echo "$OUTPUT_FILE"
echo
