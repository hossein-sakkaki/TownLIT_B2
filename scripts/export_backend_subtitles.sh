#!/usr/bin/env bash

# scripts/export_backend_subtitles.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-11-07.
# Last Update by Hossein Sakkaki on 2026-11-07.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/17_backend_subtitles.md"
APP_ROOT="$ROOT_DIR/apps/subtitles"

SOURCE_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATIONS_FILE="$(mktemp)"

trap 'rm -f "$SOURCE_FILES" "$REFERENCE_FILES" "$MIGRATIONS_FILE"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Subtitles Snapshot" \
    "Authoritative Backend Subtitles snapshot covering apps/subtitles recursively, subtitle/caption domain models, timing/cues, transcription, translation linkage, media ownership, generation workflows, APIs, serializers, services, selectors, tasks, admin, validation, provider integrations, and cross-feature subtitle references."

append_git_snapshot "$OUTPUT_FILE"

SUBTITLE_REGEX='subtitle|subtitles|caption|captions|cue|cues|transcript|transcription|timed.?text|webvtt|vtt|srt|speech.?to.?text|speech_to_text|start_ms|end_ms|start_time|end_time|language_code'
PROVIDER_REGEX='OpenAI|openai|Whisper|whisper|Deepgram|deepgram|AssemblyAI|assemblyai|Google Speech|Speech-to-Text|speech.?to.?text|Azure|AWS Transcribe|transcribe|transcription provider|model_name|prompt|LLM|llm'
MEDIA_REGEX='media|video|audio|asset|file|upload|storage|S3|CloudFront|duration|timeline|track|variant'
TRANSLATION_REGEX='translation|translations|translate|source_language|target_language|language_code|locale'

separator "$OUTPUT_FILE" "SUBTITLES ROOT"
{
    echo '```text'
    [[ -d "$APP_ROOT" ]] && echo "apps/subtitles" || echo "WARNING: apps/subtitles was not found."
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLES DIRECTORY TREE"
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
        \( -name "*.py" -o -name "*.json" -o -name "*.yaml" -o -name "*.yml" -o -name "*.toml" -o -name "*.md" -o -name "*.txt" -o -name "*.vtt" -o -name "*.srt" \) \
        -print > "$SOURCE_FILES"

    find "$APP_ROOT" \
        -type f \
        -path '*/migrations/*.py' \
        ! -name "__init__.py" \
        -print > "$MIGRATIONS_FILE"
fi

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$MIGRATIONS_FILE" -o "$MIGRATIONS_FILE"

separator "$OUTPUT_FILE" "SUBTITLES SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SOURCE_FILES" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$SOURCE_FILES"
    else
        echo "No Backend Subtitles source files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLE DOMAIN / CONTRACT INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(grep -Ein "$SUBTITLE_REGEX" "$file" 2>/dev/null | head -n 260 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLE TIMING / CUE INTEGRITY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(
            grep -Ein \
                'start_ms|end_ms|start_time|end_time|duration|sequence|order|overlap|cue|segment|timestamp|timeline|offset|timing' \
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

separator "$OUTPUT_FILE" "SUBTITLE PROVIDER / TRANSCRIPTION / AI INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(grep -Ein "$PROVIDER_REGEX" "$file" 2>/dev/null | head -n 240 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLE / TRANSLATION LINKAGE INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(grep -Ein "$TRANSLATION_REGEX" "$file" 2>/dev/null | head -n 220 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLE / MEDIA INTEGRATION INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        if grep -Eiq "$SUBTITLE_REGEX" "$file" && grep -Eiq "$MEDIA_REGEX" "$file"; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            grep -Ein "$SUBTITLE_REGEX|$MEDIA_REGEX" "$file" 2>/dev/null | head -n 240 || true
        fi
    done < "$SOURCE_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLE ASYNC / TASK / RETRY INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        if grep -Eiq "$SUBTITLE_REGEX" "$file" \
            && grep -Eiq 'celery|shared_task|task|retry|timeout|queued|processing|failed|failure|backoff|progress|job' "$file"
        then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            grep -Ein \
                'subtitle|caption|transcript|transcription|celery|shared_task|task|retry|timeout|queued|processing|failed|failure|backoff|progress|job' \
                "$file" 2>/dev/null | head -n 220 || true
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
                'apps\.subtitles|from subtitles|import subtitles|SubtitleService|SubtitleRepository|SubtitleTrack|SubtitleCue|CaptionTrack|Transcript|transcription|webvtt|\.vtt|\.srt' \
                "$file"
            then
                echo "$file" >> "$REFERENCE_FILES"
            fi
        done
fi

sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "$OUTPUT_FILE" "CROSS-FEATURE SUBTITLE REFERENCES"
{
    echo '```text'
    if [[ -s "$REFERENCE_FILES" ]]; then
        while IFS= read -r file; do
            matches="$(
                grep -Ein \
                    'apps\.subtitles|from subtitles|import subtitles|SubtitleService|SubtitleRepository|SubtitleTrack|SubtitleCue|CaptionTrack|Transcript|transcription|webvtt|\.vtt|\.srt' \
                    "$file" 2>/dev/null | head -n 160 || true
            )"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < "$REFERENCE_FILES"
    else
        echo "No additional cross-feature Subtitle references discovered."
    fi
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLES MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATIONS_FILE" ]]; then
        while IFS= read -r file; do
            echo "${file#$ROOT_DIR/}"
        done < "$MIGRATIONS_FILE"
    else
        echo "No Subtitles migrations were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SUBTITLES SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SOURCE_FILES"

echo
echo "✅ Backend Subtitles snapshot created:"
echo "$OUTPUT_FILE"
echo
