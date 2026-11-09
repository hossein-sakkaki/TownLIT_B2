#!/usr/bin/env bash

# scripts/export_backend_translations.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-21.
# Last Update by Hossein Sakkaki on 2026-10-21.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/13_backend_translations.md"
TRANSLATIONS_ROOT="$ROOT_DIR/apps/translations"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Translations Snapshot" \
    "Authoritative Backend translations snapshot covering apps/translations recursively, translation models/contracts, APIs, serializers, permissions, services, selectors, tasks, admin, language/locale handling, provider integrations, caching, and cross-feature translation usages."

append_git_snapshot "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "TRANSLATIONS ROOT"
{
    echo '```text'
    [[ -d "$TRANSLATIONS_ROOT" ]] \
        && echo "apps/translations" \
        || echo "WARNING: apps/translations was not found."
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "TRANSLATIONS DIRECTORY TREE"
{
    echo '```text'
    if [[ -d "$TRANSLATIONS_ROOT" ]]; then
        find "$TRANSLATIONS_ROOT" \
            \( -path '*/__pycache__' -o -path '*/migrations' -o -path '*/tests' -o -path '*/test' \) -prune \
            -o -type d -print \
            | sed "s|$ROOT_DIR/||" \
            | sort
    fi
    echo '```'
} >> "$OUTPUT_FILE"

if [[ -d "$TRANSLATIONS_ROOT" ]]; then
    find "$TRANSLATIONS_ROOT" \
        \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/tests/*' -o -path '*/test/*' \) -prune \
        -o -type f \
        \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" -o -name "*.txt" \) \
        -print > "$SOURCE_FILES"

    find "$TRANSLATIONS_ROOT" \
        -type f \
        -path '*/migrations/*.py' \
        ! -name "__init__.py" \
        -print > "$MIGRATIONS_FILE"
fi

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATIONS_FILE" -o "$MIGRATIONS_FILE"

separator "$OUTPUT_FILE" "TRANSLATIONS SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    else
        echo "No Backend Translation source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "TRANSLATION DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        matches="$(
            grep -En \
                '^[[:space:]]*(class|def|async[[:space:]]+def)[[:space:]]+[A-Za-z0-9_]*(Translation|Translate|Language|Locale)[A-Za-z0-9_]*|translation|translate|language_code|locale|source_language|target_language' \
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

separator "$OUTPUT_FILE" "TRANSLATION PROVIDER / AI INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        matches="$(
            grep -Ein \
                'OpenAI|openai|Anthropic|anthropic|Gemini|gemini|Google Translate|google.?translate|DeepL|deepl|Azure|Translator|translation provider|model_name|prompt|LLM|llm' \
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

separator "$OUTPUT_FILE" "TRANSLATION CACHE / ASYNC INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ -n "$file" ]] || continue
        matches="$(
            grep -Ein \
                'cache|cached|redis|dedup|idempot|hash|fingerprint|expires|ttl|celery|shared_task|retry|timeout|pending|processing|queued' \
                "$file" 2>/dev/null | head -n 180 || true
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

find "$ROOT_DIR" \
    \( \
        -path '*/.git/*' -o -path '*/.venv/*' -o -path '*/venv/*' -o -path '*/env/*' \
        -o -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/chatgpt_sources/*' \
        -o -path "$TRANSLATIONS_ROOT/*" -o -path '*/staticfiles/*' -o -path '*/media/*' \
    \) -prune \
    -o -type f -name "*.py" -print \
    | while IFS= read -r file; do
        if grep -Eiq \
            'apps\.translations|from translations|import translations|TranslationService|TranslationClient|TranslationRepository|translate_text|translate_content|translation_status|source_language|target_language' \
            "$file"
        then
            echo "$file" >> "$REFERENCE_FILES"
        fi
    done

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "$OUTPUT_FILE" "CROSS-FEATURE TRANSLATION REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(
                grep -Ein \
                    'apps\.translations|from translations|import translations|TranslationService|TranslationClient|TranslationRepository|translate_text|translate_content|translation_status|source_language|target_language' \
                    "$file" 2>/dev/null | head -n 140 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional cross-feature Translation references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "TRANSLATIONS MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATIONS_FILE" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATIONS_FILE"
    else
        echo "No Translations migrations were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "TRANSLATIONS SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Translations snapshot created:"
echo "$OUTPUT_FILE"
echo
