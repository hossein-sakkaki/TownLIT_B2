#!/usr/bin/env bash
# scripts/export_backend_accounting.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/15_backend_accounting.md"
APP_ROOT="$ROOT_DIR/apps/accounting"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Accounting Snapshot" \
    "Authoritative Backend Accounting snapshot covering apps/accounting recursively, accounting domain models, ledgers, entries, balances, reconciliation, fiscal periods, permissions, APIs, serializers, services, selectors, tasks, admin, audit behavior, and cross-feature accounting integrations."

append_git_snapshot "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ACCOUNTING ROOT"
{
    echo '```text'
    [[ -d "$APP_ROOT" ]] && echo "apps/accounting" || echo "WARNING: apps/accounting was not found."
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ACCOUNTING DIRECTORY TREE"
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

separator "$OUTPUT_FILE" "ACCOUNTING SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    else
        echo "No Accounting source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ACCOUNTING DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -Ein \
                'ledger|journal|entry|posting|chart.?of.?accounts|debit|credit|balance|reconciliation|reconcile|fiscal|period|transaction|expense|income|revenue|liability|asset|equity|payable|receivable|allocation|fund|restricted|unrestricted' \
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

separator "$OUTPUT_FILE" "ACCOUNTING INTEGRITY / POSTING / IDEMPOTENCY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -Ein \
                'atomic|transaction\.atomic|select_for_update|constraint|CheckConstraint|UniqueConstraint|idempot|dedup|posted|posting|reversal|reverse|immutable|snapshot|lock|balanced|debit|credit' \
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

separator "$OUTPUT_FILE" "ACCOUNTING PERMISSIONS / AUDIT / ADMIN INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -Ein \
                'permission|role|staff|admin|audit|approved|approval|authorized|authorize|created_by|updated_by|posted_by|reviewed_by|approved_by' \
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

separator "$OUTPUT_FILE" "MONEY / CURRENCY / PRECISION INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(
            grep -Ein \
                'Decimal|DecimalField|currency|amount|minor.?unit|round|quantize|precision|exchange.?rate|fx|tax|gst|pst|vat' \
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
                'apps\.accounting|from accounting|import accounting|AccountingService|AccountingRepository|Ledger|JournalEntry|ChartOfAccounts|reconciliation|posting' \
                "$file"
            then
                echo "$file" >> "$REFERENCE_FILES"
            fi
        done
fi

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "$OUTPUT_FILE" "CROSS-FEATURE ACCOUNTING REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(
                grep -Ein \
                    'apps\.accounting|from accounting|import accounting|AccountingService|AccountingRepository|Ledger|JournalEntry|ChartOfAccounts|reconciliation|posting' \
                    "$file" 2>/dev/null | head -n 150 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional cross-feature Accounting references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ACCOUNTING MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATIONS_FILE" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATIONS_FILE"
    else
        echo "No Accounting migrations were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "ACCOUNTING SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Accounting snapshot created:"
echo "$OUTPUT_FILE"
echo
