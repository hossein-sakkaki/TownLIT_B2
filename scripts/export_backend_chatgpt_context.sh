#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ROOT_DIR="$(
    git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null
)"; then
    :
else
    ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"

echo
echo "============================================================"
echo " TownLIT Backend — ChatGPT Context Export"
echo "============================================================"
echo
echo "Repository:"
echo "$ROOT_DIR"
echo

mkdir -p "$OUTPUT_DIR"

echo "------------------------------------------------------------"
echo " [1/9] Project Foundation"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_foundation.sh"

echo "------------------------------------------------------------"
echo " [2/9] Core Domain Models"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_core_models.sh"

echo "------------------------------------------------------------"
echo " [3/9] Shared Infrastructure"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_shared_infrastructure.sh"

echo "------------------------------------------------------------"
echo " [4/9] Identity / Profile API"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_identity_api.sh"

echo "------------------------------------------------------------"
echo " [5/9] Organizations"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_organizations.sh"

echo "------------------------------------------------------------"
echo " [6/9] Conversation"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_conversation.sh"

echo "------------------------------------------------------------"
echo " [7/9] Audio Catalog"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_audio_catalog.sh"

echo "------------------------------------------------------------"
echo " [8/9] Subscriptions / Entitlements"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_subscriptions_entitlements.sh"

echo "------------------------------------------------------------"
echo " [9/9] Square and Stream"
echo "------------------------------------------------------------"
/bin/bash "$SCRIPT_DIR/export_backend_square_streams.sh"

echo
echo "============================================================"
echo " SNAPSHOT SUMMARY"
echo "============================================================"
echo

total_bytes=0
total_lines=0

for file in "$OUTPUT_DIR"/*.md; dos
    [[ -f "$file" ]] || continue

    filename="$(basename "$file")"
    size_human="$(du -h "$file" | awk '{print $1}')"
    size_bytes="$(wc -c < "$file" | tr -d ' ')"
    lines="$(wc -l < "$file" | tr -d ' ')"

    total_bytes=$((total_bytes + size_bytes))
    total_lines=$((total_lines + lines))

    printf "%-50s %8s   %9s lines\n" \
        "$filename" \
        "$size_human" \
        "$lines"
done

echo
echo "------------------------------------------------------------"
echo "Total lines: $total_lines"

if command -v numfmt >/dev/null 2>&1; then
    echo "Total size:  $(numfmt --to=iec "$total_bytes")"
else
    total_mb="$(awk "BEGIN {printf \"%.2f\", $total_bytes / 1024 / 1024}")"
    echo "Total size:  ${total_mb} MB"
fi

echo "============================================================"
echo " ✅ ALL BACKEND CHATGPT SNAPSHOTS UPDATED"
echo "============================================================"
echo
echo "Output directory:"
echo "$OUTPUT_DIR"
echo
