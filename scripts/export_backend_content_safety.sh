#!/usr/bin/env bash

# scripts/export_backend_content_safety.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-10-17.
# Last Update by Hossein Sakkaki on 2026-10-17.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ROOT_DIR="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null)"; then :; else ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"; fi

OUTPUT_DIR="$ROOT_DIR/chatgpt_sources"
OUTPUT_FILE="$OUTPUT_DIR/11_backend_content_safety.md"
mkdir -p "$OUTPUT_DIR"

OWNED_ROOTS="$(mktemp)"
SOURCE_FILES="$(mktemp)"
AI_FILES="$(mktemp)"
REFERENCE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"
FILTERED_ROOTS="$(mktemp)"
trap 'rm -f "$OWNED_ROOTS" "$SOURCE_FILES" "$AI_FILES" "$REFERENCE_FILES" "$MIGRATION_FILES" "$FILTERED_ROOTS"' EXIT

CONTENT_SAFETY_REGEX='content_safety|content safety|ContentSafety|Content Safety'
SAFETY_REGEX='content_safety|ContentSafety|moderation|Moderation|SafetyVerdict|SafetyDecision|SafetyResult|SafetyPolicy|PolicyViolation|toxicity|Toxicity|harassment|Harassment|hate speech|HateSpeech|self harm|SelfHarm|sexual content|SexualContent|violence|Violence|abuse|Abuse'
AI_REGEX='OpenAI|openai|Anthropic|anthropic|Gemini|gemini|Vertex|vertex|LLM|llm|AIClient|AiClient|ai_client|classifier|classification|classify|inference|prompt|Prompt|model_name|modelName|response_format|structured_output'

separator() { printf '\n---\n\n# %s\n\n' "$1" >> "$OUTPUT_FILE"; }

ignored() {
  local p="$1"
  [[ "$p" == *"/.git/"* || "$p" == *"/.venv/"* || "$p" == *"/venv/"* || "$p" == *"/__pycache__/"* || "$p" == *"/.pytest_cache/"* || "$p" == *"/chatgpt_sources/"* || "$p" == *"/staticfiles/"* || "$p" == *"/media/"* || "$p" == *"/.env"* || "$p" == *"/secrets/"* || "$p" == *"/private_keys/"* ]]
}

supported() {
  case "$1" in *.py|*.sh|*.json|*.yml|*.yaml|*.toml|*.md|*.txt) return 0 ;; *) return 1 ;; esac
}

append_file() {
  local file="$1" rel="${1#$ROOT_DIR/}" ext="${1##*.}" lang="text"
  case "$ext" in py) lang="python";; sh) lang="bash";; json) lang="json";; yml|yaml) lang="yaml";; toml) lang="toml";; md) lang="markdown";; esac
  { printf '\n## FILE: %s\n\n```%s\n' "$rel" "$lang"; cat "$file"; printf '\n```\n'; } >> "$OUTPUT_FILE"
}

in_owned_root() {
  local file="$1" root
  while IFS= read -r root; do [[ -n "$root" ]] || continue; [[ "$file" == "$root" || "$file" == "$root"/* ]] && return 0; done < "$OWNED_ROOTS"
  return 1
}

cat > "$OUTPUT_FILE" <<'HDR'
# TownLIT Backend — Content Safety Snapshot

**Purpose:** Authoritative Backend snapshot for TownLIT `content_safety`, including complete owned source, safety policies/rules, moderation decisions, post/comment/content integrations, async processing, API/admin wiring, and AI-assisted review/classification source used by the safety pipeline.

**Security:** Environment files, secrets, keys, media and generated artifacts are excluded.

**Migrations:** Inventoried only; runtime source remains authoritative for current behavior.
HDR

{
  echo '```text'
  echo "Repository: $ROOT_DIR"
  echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %z')"
  if git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Branch: $(git -C "$ROOT_DIR" branch --show-current 2>/dev/null || true)"
    echo "Commit: $(git -C "$ROOT_DIR" rev-parse HEAD 2>/dev/null || true)"
  fi
  echo '```'
} >> "$OUTPUT_FILE"

# Discover dedicated content_safety roots.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
  [[ -d "$base" ]] || continue
  while IFS= read -r dir; do
    ignored "$dir/" && continue
    name="$(basename "$dir" | tr '[:upper:]' '[:lower:]' | tr -d '_-')"
    [[ "$name" == "contentsafety" ]] && echo "$dir" >> "$OWNED_ROOTS"
  done < <(find "$base" -type d -print 2>/dev/null)
done
sort -u "$OWNED_ROOTS" -o "$OWNED_ROOTS"

# Remove nested duplicate roots.
while IFS= read -r candidate; do
  [[ -n "$candidate" ]] || continue
  nested=0
  while IFS= read -r existing; do [[ -n "$existing" ]] || continue; [[ "$candidate" == "$existing"/* ]] && nested=1 && break; done < "$FILTERED_ROOTS"
  [[ "$nested" -eq 0 ]] && echo "$candidate" >> "$FILTERED_ROOTS"
done < "$OWNED_ROOTS"
mv "$FILTERED_ROOTS" "$OWNED_ROOTS"

separator "CONTENT SAFETY OWNED ROOTS"
{
  echo '```text'
  if [[ -s "$OWNED_ROOTS" ]]; then while IFS= read -r d; do echo "${d#$ROOT_DIR/}"; done < "$OWNED_ROOTS"; else echo "No dedicated content_safety root discovered."; fi
  echo '```'
} >> "$OUTPUT_FILE"

# Complete source under owned roots.
while IFS= read -r dir; do
  [[ -d "$dir" ]] || continue
  while IFS= read -r file; do
    ignored "$file" && continue; supported "$file" || continue
    if [[ "$file" == */migrations/* ]]; then echo "$file" >> "$MIGRATION_FILES"; else echo "$file" >> "$SOURCE_FILES"; fi
  done < <(find "$dir" -type f -print 2>/dev/null)
done < "$OWNED_ROOTS"

# Named source outside owned roots.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
  [[ -d "$base" ]] || continue
  while IFS= read -r file; do
    ignored "$file" && continue; supported "$file" || continue
    if [[ "$file" == */migrations/* ]]; then echo "$file" >> "$MIGRATION_FILES"; else echo "$file" >> "$SOURCE_FILES"; fi
  done < <(find "$base" -type f \( -iname '*content_safety*.py' -o -iname '*content-safety*.py' -o -iname '*contentsafety*.py' -o -iname '*moderation*.py' -o -iname '*safety_policy*.py' -o -iname '*safety_rules*.py' -o -iname '*content_safety*.json' -o -iname '*content_safety*.yml' -o -iname '*content_safety*.yaml' -o -iname '*content_safety*.md' \) -print 2>/dev/null)
done

# AI-assisted safety source: require both a safety signal and an AI/provider/classifier signal.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
  [[ -d "$base" ]] || continue
  while IFS= read -r file; do
    ignored "$file" && continue; supported "$file" || continue; [[ "$file" == */migrations/* ]] && continue
    if grep -Eiq "$SAFETY_REGEX" "$file" && grep -Eiq "$AI_REGEX" "$file"; then echo "$file" >> "$AI_FILES"; fi
  done < <(find "$base" -type f \( -name '*.py' -o -name '*.json' -o -name '*.yml' -o -name '*.yaml' -o -name '*.toml' -o -name '*.md' -o -name '*.txt' \) -print 2>/dev/null)
done
cat "$AI_FILES" >> "$SOURCE_FILES"

# Architecture-level integration files.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
  [[ -d "$base" ]] || continue
  while IFS= read -r file; do
    ignored "$file" && continue; [[ "$file" == *.py ]] || continue; [[ "$file" == */migrations/* ]] && continue; in_owned_root "$file" && continue
    case "$(basename "$file")" in
      urls.py|admin.py|apps.py|tasks.py|signals.py|services.py|selectors.py|permissions.py|serializers.py|views.py|api.py|events.py|handlers.py|consumers.py|routing.py|moderation.py|validators.py|validation.py|policies.py|policy.py|filters.py)
        grep -Eiq "$CONTENT_SAFETY_REGEX|SafetyVerdict|SafetyDecision|PolicyViolation" "$file" && echo "$file" >> "$SOURCE_FILES"
        ;;
    esac
  done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done

sort -u "$SOURCE_FILES" -o "$SOURCE_FILES"
sort -u "$AI_FILES" -o "$AI_FILES"
sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "CONTENT SAFETY SOURCE INVENTORY"
{ echo '```text'; if [[ -s "$SOURCE_FILES" ]]; then while IFS= read -r f; do echo "${f#$ROOT_DIR/}"; done < "$SOURCE_FILES"; else echo "No Content Safety source discovered."; fi; echo '```'; } >> "$OUTPUT_FILE"

separator "AI-ASSISTED SAFETY SOURCE INVENTORY"
{ echo '```text'; if [[ -s "$AI_FILES" ]]; then while IFS= read -r f; do echo "${f#$ROOT_DIR/}"; done < "$AI_FILES"; else echo "No focused AI-assisted safety source discovered."; fi; echo '```'; } >> "$OUTPUT_FILE"

separator "CONTENT SAFETY DOMAIN / CONTRACT INDEX"
{
  echo '```text'
  while IFS= read -r file; do
    [[ "$file" == *.py ]] || continue
    matches="$(grep -En 'ContentSafety|content_safety|SafetyVerdict|SafetyDecision|SafetyResult|SafetyPolicy|PolicyViolation|Moderation|moderation' "$file" 2>/dev/null | head -n 220 || true)"
    [[ -n "$matches" ]] && { echo; echo "FILE: ${file#$ROOT_DIR/}"; echo "$matches"; }
  done < "$SOURCE_FILES"
  echo; echo '```'
} >> "$OUTPUT_FILE"

separator "AI / PROVIDER / PROMPT / CLASSIFIER INDEX"
{
  echo '```text'
  while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    matches="$(grep -Ein 'OpenAI|Anthropic|Gemini|Vertex|LLM|AIClient|ai_client|classifier|classification|classify|prompt|response_format|structured_output|model_name|moderation' "$file" 2>/dev/null | head -n 220 || true)"
    [[ -n "$matches" ]] && { echo; echo "FILE: ${file#$ROOT_DIR/}"; echo "$matches"; }
  done < "$AI_FILES"
  echo; echo '```'
} >> "$OUTPUT_FILE"

separator "POST / COMMENT / CONTENT INTEGRATION INDEX"
{
  echo '```text'
  while IFS= read -r file; do
    [[ "$file" == *.py ]] || continue
    if grep -Eiq 'post|comment|reply|stream|media|caption|content|profile|organization' "$file" && grep -Eiq "$CONTENT_SAFETY_REGEX|SafetyVerdict|SafetyDecision|PolicyViolation|moderation" "$file"; then
      echo; echo "FILE: ${file#$ROOT_DIR/}"
      grep -Ein 'post|comment|reply|stream|media|caption|content|profile|organization|content_safety|ContentSafety|SafetyVerdict|SafetyDecision|PolicyViolation|moderation' "$file" 2>/dev/null | head -n 220 || true
    fi
  done < "$SOURCE_FILES"
  echo; echo '```'
} >> "$OUTPUT_FILE"

separator "ASYNC / TASK / RETRY / FAILURE INDEX"
{
  echo '```text'
  while IFS= read -r file; do
    [[ "$file" == *.py ]] || continue
    if grep -Eiq 'celery|shared_task|task|retry|timeout|exception|failure|failed|pending|processing|queued' "$file" && grep -Eiq "$SAFETY_REGEX" "$file"; then
      echo; echo "FILE: ${file#$ROOT_DIR/}"
      grep -Ein 'content_safety|moderation|safety|celery|shared_task|task|retry|timeout|exception|failure|failed|pending|processing|queued' "$file" 2>/dev/null | head -n 220 || true
    fi
  done < "$SOURCE_FILES"
  echo; echo '```'
} >> "$OUTPUT_FILE"

# Cross-feature direct references as snippets.
for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
  [[ -d "$base" ]] || continue
  while IFS= read -r file; do
    ignored "$file" && continue; [[ "$file" == *.py ]] || continue; [[ "$file" == */migrations/* ]] && continue
    if grep -Eiq "$CONTENT_SAFETY_REGEX|SafetyVerdict|SafetyDecision|PolicyViolation" "$file" && ! grep -Fxq "$file" "$SOURCE_FILES" 2>/dev/null; then echo "$file" >> "$REFERENCE_FILES"; fi
  done < <(find "$base" -type f -name '*.py' -print 2>/dev/null)
done
sort -u "$REFERENCE_FILES" -o "$REFERENCE_FILES"

separator "CROSS-FEATURE CONTENT SAFETY REFERENCES"
{
  echo '```text'
  if [[ -s "$REFERENCE_FILES" ]]; then
    while IFS= read -r file; do
      matches="$(grep -En "$CONTENT_SAFETY_REGEX|SafetyVerdict|SafetyDecision|PolicyViolation" "$file" 2>/dev/null | head -n 140 || true)"
      [[ -n "$matches" ]] && { echo; echo "FILE: ${file#$ROOT_DIR/}"; echo "$matches"; }
    done < "$REFERENCE_FILES"
  else echo "No additional cross-feature Content Safety references discovered."; fi
  echo; echo '```'
} >> "$OUTPUT_FILE"

separator "CONTENT SAFETY MIGRATION INVENTORY"
{ echo '```text'; if [[ -s "$MIGRATION_FILES" ]]; then while IFS= read -r f; do echo "${f#$ROOT_DIR/}"; done < "$MIGRATION_FILES"; else echo "No Content Safety migrations discovered."; fi; echo '```'; } >> "$OUTPUT_FILE"

separator "CONTENT SAFETY COMPLETE SOURCE"
while IFS= read -r file; do [[ -n "$file" ]] || continue; append_file "$file"; done < "$SOURCE_FILES"

echo
echo "✅ Backend Content Safety snapshot created:"
echo "$OUTPUT_FILE"
echo
