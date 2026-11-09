#!/usr/bin/env bash
# scripts/export_backend_advancement.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/16_backend_advancement.md"
APP_ROOT="$ROOT_DIR/apps/advancement"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Advancement Snapshot" \
    "Authoritative Backend Advancement snapshot covering apps/advancement recursively, donors/supporters, gifts, pledges, campaigns, appeals, grants, stewardship, acknowledgements, receipts, relationships, permissions, APIs, serializers, services, selectors, tasks, admin, and cross-feature advancement integrations."

append_git_snapshot "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT ROOT"
{
    echo '```text'
    [[ -d "$APP_ROOT" ]] && echo "apps/advancement" || echo "WARNING: apps/advancement was not found."
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT DIRECTORY TREE"
{
    echo '```text'
    if [[ -d "$APP_ROOT" ]]; then
        find "$APP_ROOT" \
            \( -path '*/__pycache__' -o -path '*/migrations' -o -path '*/tests' -o -path '*/test' \) -prune \
            -o -type d -print \
            | sed "s|$ROOT_DIR/||" \
            | sort
    fi
    echo '```'
} >> "$OUTPUT_FILE"

if [[ -d "$APP_ROOT" ]]; then
    find "$APP_ROOT" \
        \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' -o -path '*/test/*' \) -prune \
        -o -type f \
        \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" -o -name "*.txt" \) \
        -print > "$SOURCE_FILES"

    find "$APP_ROOT" \
        -type f \
        -path '*/migrations/*.py' \
        ! -name "__init__.py" \
        -print > "$MIGRATIONS_FILE"
fi

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATIONS_FILE" -o "$MIGRATIONS_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    else
        echo "No Advancement source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -Ein \
                'donor|supporter|constituent|gift|donation|pledge|campaign|appeal|grant|fundraising|fundraiser|stewardship|acknowledg|receipt|designation|allocation|commitment|prospect|relationship|engagement|sponsor|sponsorship' \
                "$file" 2>/dev/null | head -n 260 || true
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

separator "$OUTPUT_FILE" "GIFT / MONEY / RECEIPT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(
            grep -Ein \
                'Decimal|DecimalField|amount|currency|gift|donation|pledge|receipt|tax.?receipt|charitable.?receipt|designation|fund|restricted|unrestricted|refund|reversal|payment|processor|stripe' \
                "$file" 2>/dev/null | head -n 240 || true
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

separator "$OUTPUT_FILE" "DONOR PRIVACY / CONSENT / COMMUNICATION INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(
            grep -Ein \
                'email|phone|address|anonymous|anonymity|privacy|consent|opt.?in|opt.?out|communication|contact|preferred.?language|do.?not.?contact|receipt.?name|legal.?name|tax.?id' \
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

separator "$OUTPUT_FILE" "ADVANCEMENT WORKFLOW / APPROVAL / IDEMPOTENCY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -Ein \
                'atomic|transaction\.atomic|select_for_update|idempot|dedup|status|pending|approved|approval|review|posted|fulfilled|canceled|cancelled|refund|reversal|immutable|audit' \
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

if [[ -d "$ROOT_DIR/apps" ]]; then
    find "$ROOT_DIR/apps" \
        \( -path "$APP_ROOT/*" -o -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/chatgpt_sources/*' \) -prune \
        -o -type f -name "*.py" -print \
        | while IFS= read -r file; do
            if grep -Eiq \
                'apps\.advancement|from advancement|import advancement|AdvancementService|Donor|Donation|Gift|Pledge|Campaign|Appeal|Grant|Fundraising|Stewardship' \
                "$file"
            then
                echo "$file" >> "$REFERENCE_FILES"
            fi
        done
fi

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "$OUTPUT_FILE" "CROSS-FEATURE ADVANCEMENT REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(
                grep -Ein \
                    'apps\.advancement|from advancement|import advancement|AdvancementService|Donor|Donation|Gift|Pledge|Campaign|Appeal|Grant|Fundraising|Stewardship' \
                    "$file" 2>/dev/null | head -n 150 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional cross-feature Advancement references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATIONS_FILE" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATIONS_FILE"
    else
        echo "No Advancement migrations were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ADVANCEMENT SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Advancement snapshot created:"
echo "$OUTPUT_FILE"
echo
