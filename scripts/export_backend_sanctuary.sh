#!/usr/bin/env bash

# scripts/export_backend_sanctuary.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-01.
# Last Update by Hossein Sakkaki on 2026-10-01.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"
OUTPUT_FILE="$OUTPUT_DIR/09_backend_sanctuary.md"

mkdir -p "$OUTPUT_DIR"

TMP_ROOTS="$(mktemp)"
TMP_SOURCE="$(mktemp)"
TMP_REFS="$(mktemp)"
TMP_MIGRATIONS="$(mktemp)"
trap 'rm -f "$TMP_ROOTS" "$TMP_SOURCE" "$TMP_REFS" "$TMP_MIGRATIONS"' EXIT

separator() {
  printf '\n---\n\n# %s\n\n' "$1" >> "$OUTPUT_FILE"
}

append_file() {
  local file="$1"
  local rel="${file#$ROOT_DIR/}"
  local lang="text"
  case "$file" in
    *.py) lang="python" ;;
    *.sh) lang="bash" ;;
    *.json) lang="json" ;;
    *.yml|*.yaml) lang="yaml" ;;
    *.toml) lang="toml" ;;
    *.md) lang="markdown" ;;
  esac
  {
    printf '\n## FILE: %s\n\n```%s\n' "$rel" "$lang"
    cat "$file"
    printf '\n```\n'
  } >> "$OUTPUT_FILE"
}

supported_file() {
  case "$1" in
    *.py|*.sh|*.json|*.yml|*.yaml|*.toml|*.md|*.txt) return 0 ;;
    *) return 1 ;;
  esac
}

ignored_path() {
  case "$1" in
    */.git/*|*/.venv/*|*/venv/*|*/node_modules/*|*/__pycache__/*|*/.pytest_cache/*|*/chatgpt_sources/*) return 0 ;;
    *) return 1 ;;
  esac
}

cat > "$OUTPUT_FILE" <<'HEADER'
# TownLIT Backend — Sanctuary Snapshot

Authoritative Backend snapshot for Sanctuary. It includes complete Sanctuary-owned runtime source, important routing/admin/service/task/realtime integrations, cross-feature references, and migration inventory.

Migration source is inventoried rather than embedded as current-state runtime authority.
HEADER

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

# Discover Sanctuary-owned directories. Keep only highest matching roots.
find "$ROOT_DIR" \
  -type d \
  -iname '*sanctuary*' \
  -print 2>/dev/null \
  | sort \
  | while IFS= read -r candidate; do
      ignored_path "$candidate/" && continue
      rel="${candidate#$ROOT_DIR/}"
      case "$rel" in
        apps/*|config/*|townlit/*) ;;
        *) continue ;;
      esac

      nested=0
      while IFS= read -r existing; do
        [[ -n "$existing" ]] || continue
        if [[ "$candidate" == "$existing"/* ]]; then
          nested=1
          break
        fi
      done < "$TMP_ROOTS"

      [[ "$nested" -eq 1 ]] || echo "$candidate" >> "$TMP_ROOTS"
    done

sort -u "$TMP_ROOTS" -o "$TMP_ROOTS"

separator "SANCTUARY OWNED ROOTS"
{
  echo '```text'
  if [[ -s "$TMP_ROOTS" ]]; then
    while IFS= read -r dir; do echo "${dir#$ROOT_DIR/}"; done < "$TMP_ROOTS"
  else
    echo "No Sanctuary-named directory discovered; file/reference discovery will still run."
  fi
  echo '```'
} >> "$OUTPUT_FILE"

# Complete source under Sanctuary roots.
while IFS= read -r dir; do
  [[ -d "$dir" ]] || continue
  find "$dir" -type f -print 2>/dev/null | while IFS= read -r file; do
    ignored_path "$file" && continue
    supported_file "$file" || continue
    if [[ "$file" == */migrations/* ]]; then
      echo "$file" >> "$TMP_MIGRATIONS"
    else
      echo "$file" >> "$TMP_SOURCE"
    fi
  done
done < "$TMP_ROOTS"

# Sanctuary-named source files anywhere in Backend.
find "$ROOT_DIR" -type f \
  \( -iname '*sanctuary*.py' -o -iname '*sanctuary*.sh' -o -iname '*sanctuary*.json' \
     -o -iname '*sanctuary*.yml' -o -iname '*sanctuary*.yaml' -o -iname '*sanctuary*.toml' \
     -o -iname '*sanctuary*.md' -o -iname '*sanctuary*.txt' \) \
  -print 2>/dev/null \
  | while IFS= read -r file; do
      ignored_path "$file" && continue
      if [[ "$file" == */migrations/* ]]; then
        echo "$file" >> "$TMP_MIGRATIONS"
      else
        echo "$file" >> "$TMP_SOURCE"
      fi
    done

# Full integration files for common wiring points when Sanctuary is referenced.
for base in "$ROOT_DIR/config" "$ROOT_DIR/townlit" "$ROOT_DIR/apps"; do
  [[ -d "$base" ]] || continue
  find "$base" -type f -name '*.py' -print 2>/dev/null | while IFS= read -r file; do
    ignored_path "$file" && continue
    [[ "$file" == */migrations/* ]] && continue
    grep -Eiq 'Sanctuary|sanctuary' "$file" || continue
    rel="${file#$ROOT_DIR/}"
    case "$rel" in
      */urls.py|*/admin.py|*/apps.py|*/tasks.py|*/routing.py|*/consumers.py|*/signals.py|*/services.py|*/selectors.py|*/permissions.py|*/serializers.py|*/views.py|*/api.py|*/handlers.py|*/events.py|*/websocket*.py)
        echo "$file" >> "$TMP_SOURCE"
        ;;
      *)
        echo "$file" >> "$TMP_REFS"
        ;;
    esac
  done
done

sort -u "$TMP_SOURCE" -o "$TMP_SOURCE"
sort -u "$TMP_REFS" -o "$TMP_REFS"
sort -u "$TMP_MIGRATIONS" -o "$TMP_MIGRATIONS"

separator "SANCTUARY SOURCE INVENTORY"
{
  echo '```text'
  if [[ -s "$TMP_SOURCE" ]]; then
    while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$TMP_SOURCE"
  else
    echo "No Sanctuary source files discovered."
  fi
  echo '```'
} >> "$OUTPUT_FILE"

separator "SANCTUARY DOMAIN / CONTRACT INDEX"
{
  echo '```text'
  while IFS= read -r file; do
    [[ "$file" == *.py ]] || continue
    matches="$(grep -En 'Sanctuary|sanctuary|Review|Appeal|Reviewer|Vote|Moderation|Report' "$file" 2>/dev/null | head -n 120 || true)"
    if [[ -n "$matches" ]]; then
      echo
      echo "FILE: ${file#$ROOT_DIR/}"
      echo "$matches"
    fi
  done < "$TMP_SOURCE"
  echo
  echo '```'
} >> "$OUTPUT_FILE"

separator "CROSS-FEATURE SANCTUARY REFERENCES"
{
  echo '```text'
  if [[ -s "$TMP_REFS" ]]; then
    while IFS= read -r file; do
      matches="$(grep -En 'Sanctuary|sanctuary' "$file" 2>/dev/null | head -n 80 || true)"
      if [[ -n "$matches" ]]; then
        echo
        echo "FILE: ${file#$ROOT_DIR/}"
        echo "$matches"
      fi
    done < "$TMP_REFS"
  else
    echo "No additional Sanctuary references discovered."
  fi
  echo
  echo '```'
} >> "$OUTPUT_FILE"

separator "SANCTUARY MIGRATION INVENTORY"
{
  echo '```text'
  if [[ -s "$TMP_MIGRATIONS" ]]; then
    while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$TMP_MIGRATIONS"
  else
    echo "No Sanctuary migration files discovered."
  fi
  echo '```'
} >> "$OUTPUT_FILE"

separator "SANCTUARY SOURCE"
while IFS= read -r file; do
  [[ -n "$file" ]] || continue
  append_file "$file"
done < "$TMP_SOURCE"

echo
echo "✅ Backend Sanctuary snapshot created:"
echo "$OUTPUT_FILE"
