#!/usr/bin/env bash

# scripts/export_backend_data_protection.sh
# TownLIT
#
# Created by Hossein Sakkaki on 2026-11-04.
# Last Update by Hossein Sakkaki on 2026-11-04.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/_chatgpt_backend_common.sh"

OUTPUT_FILE="$OUTPUT_DIR/14_backend_data_protection.md"

MODEL_FILES="$(mktemp)"
SECURITY_FILES="$(mktemp)"
SENSITIVE_USAGE_FILES="$(mktemp)"
MIGRATION_FILES="$(mktemp)"

trap 'rm -f "$MODEL_FILES" "$SECURITY_FILES" "$SENSITIVE_USAGE_FILES" "$MIGRATION_FILES"' EXIT

write_standard_header \
    "$OUTPUT_FILE" \
    "TownLIT Backend — Data Protection & Field Encryption Snapshot" \
    "Authoritative Backend snapshot for auditing sensitive-data storage and implementing field-level encryption. Includes all application model source, existing crypto/security/key-management source, sensitive-field API/serializer/admin/service usage, database/security/logging configuration references, and migration inventory."

append_git_snapshot "$OUTPUT_FILE"

SENSITIVE_REGEX='email|e_mail|phone|mobile|telephone|date_of_birth|birth_date|birthday|dob|address|postal|zip_code|postcode|legal_name|first_name|middle_name|last_name|full_name|passport|government_id|identity_document|verification_document|tax_id|sin|ssn|national_id|recovery|totp|otp_secret|api_key|access_token|refresh_token|secret|private_note|pastoral|financial|bank|payment|card|health|medical'
CRYPTO_REGEX='encrypt|encrypted|encryption|decrypt|decrypted|cipher|AES|GCM|Fernet|cryptography|HMAC|hashlib|keyring|KMS|Vault|blind.?index|lookup.?hash|pepper|nonce|iv'

if [[ -d "$ROOT_DIR/apps" ]]; then
    find "$ROOT_DIR/apps" \
        \( -path '*/.git/*' -o -path '*/.venv/*' -o -path '*/venv/*' -o -path '*/env/*' -o -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/chatgpt_sources/*' \) -prune \
        -o -type f \( -name "models.py" -o -path "*/models/*.py" \) -print > "$MODEL_FILES"
fi

sort -u "$MODEL_FILES" -o "$MODEL_FILES"

separator "$OUTPUT_FILE" "APPLICATION MODEL SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$MODEL_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$MODEL_FILES"
    else
        echo "No application model files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "COMPLETE APPLICATION MODEL SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$MODEL_FILES"

separator "$OUTPUT_FILE" "SENSITIVE / PII FIELD INDEX"
{
    echo '```text'
    while IFS= read -r file; do
        matches="$(grep -Ein "$SENSITIVE_REGEX" "$file" 2>/dev/null | head -n 260 || true)"
        if [[ -n "$matches" ]]; then
            echo
            echo "FILE: ${file#$ROOT_DIR/}"
            echo "$matches"
        fi
    done < "$MODEL_FILES"
    echo
    echo '```'
} >> "$OUTPUT_FILE"

for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        if echo "$file" | grep -Eiq '/(security|crypto|cryptography|encryption|privacy|key_management|keys|kms|vault)/' || grep -Eiq "$CRYPTO_REGEX" "$file"; then
            echo "$file" >> "$SECURITY_FILES"
        fi
    done < <(find "$base" \( -path '*/__pycache__/*' -o -path '*/migrations/*' -o -path '*/chatgpt_sources/*' \) -prune -o -type f -name "*.py" -print)
done

sort -u "$SECURITY_FILES" -o "$SECURITY_FILES"

separator "$OUTPUT_FILE" "EXISTING CRYPTO / SECURITY SOURCE INVENTORY"
{
    echo '```text'
    if [[ -s "$SECURITY_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$SECURITY_FILES"
    else
        echo "No existing crypto/security implementation was discovered by the focused matcher."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "EXISTING CRYPTO / SECURITY SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SECURITY_FILES"

for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
    [[ -d "$base" ]] || continue
    while IFS= read -r file; do
        [[ "$file" == *.py ]] || continue
        [[ "$file" == */migrations/* ]] && continue
        case "$(basename "$file")" in
            serializers.py|views.py|api.py|services.py|selectors.py|admin.py|forms.py|tasks.py|signals.py|permissions.py|validators.py)
                if grep -Eiq "$SENSITIVE_REGEX|$CRYPTO_REGEX" "$file"; then echo "$file" >> "$SENSITIVE_USAGE_FILES"; fi
                ;;
        esac
    done < <(find "$base" \( -path '*/__pycache__/*' -o -path '*/migrations/*' \) -prune -o -type f -name "*.py" -print)
done

sort -u "$SENSITIVE_USAGE_FILES" -o "$SENSITIVE_USAGE_FILES"

separator "$OUTPUT_FILE" "SENSITIVE DATA API / SERIALIZER / SERVICE INVENTORY"
{
    echo '```text'
    if [[ -s "$SENSITIVE_USAGE_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$SENSITIVE_USAGE_FILES"
    else
        echo "No focused sensitive-data usage files were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "SENSITIVE DATA API / SERIALIZER / SERVICE SOURCE"
while IFS= read -r file; do
    [[ -n "$file" ]] || continue
    append_file "$OUTPUT_FILE" "$file"
done < "$SENSITIVE_USAGE_FILES"

separator "$OUTPUT_FILE" "DATABASE / SECURITY / LOGGING CONFIG REFERENCES"
{
    echo '```text'
    for base in "$ROOT_DIR/config" "$ROOT_DIR/townlit"; do
        [[ -d "$base" ]] || continue
        while IFS= read -r file; do
            matches="$(grep -Ein 'DATABASES|DATABASE_URL|mysql|postgres|ssl|TLS|SECURE_|FIELD_ENCRYPT|ENCRYPTION|KMS|VAULT|KEY_ID|KEY_VERSION|LOGGING|SENTRY|backup|snapshot' "$file" 2>/dev/null | head -n 220 || true)"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < <(find "$base" -type f -name "*.py" -print 2>/dev/null)
    done
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "AUTHENTICATION / PASSWORD / TOKEN HANDLING INDEX"
{
    echo '```text'
    for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit"; do
        [[ -d "$base" ]] || continue
        while IFS= read -r file; do
            matches="$(grep -Ein 'set_password|check_password|make_password|PasswordHasher|access_token|refresh_token|api_key|totp|recovery|secret' "$file" 2>/dev/null | head -n 180 || true)"
            if [[ -n "$matches" ]]; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                echo "$matches"
            fi
        done < <(find "$base" \( -path '*/__pycache__/*' -o -path '*/migrations/*' \) -prune -o -type f -name "*.py" -print)
    done
    echo
    echo '```'
} >> "$OUTPUT_FILE"

separator "$OUTPUT_FILE" "POTENTIAL PII / SECRET LOGGING INDEX"
{
    echo '```text'
    for base in "$ROOT_DIR/apps" "$ROOT_DIR/townlit" "$ROOT_DIR/config"; do
        [[ -d "$base" ]] || continue
        while IFS= read -r file; do
            if grep -Eiq 'logger|logging|sentry|breadcrumb' "$file" && grep -Eiq "$SENSITIVE_REGEX|token|secret" "$file"; then
                echo
                echo "FILE: ${file#$ROOT_DIR/}"
                grep -Ein 'logger|logging|sentry|breadcrumb|email|phone|birth|address|name|token|secret|passport|identity|verification' "$file" 2>/dev/null | head -n 180 || true
            fi
        done < <(find "$base" \( -path '*/__pycache__/*' -o -path '*/migrations/*' \) -prune -o -type f -name "*.py" -print)
    done
    echo
    echo '```'
} >> "$OUTPUT_FILE"

if [[ -d "$ROOT_DIR/apps" ]]; then
    find "$ROOT_DIR/apps" -type f -path '*/migrations/*.py' ! -name "__init__.py" -print > "$MIGRATION_FILES"
fi

sort -u "$MIGRATION_FILES" -o "$MIGRATION_FILES"

separator "$OUTPUT_FILE" "APPLICATION MIGRATION INVENTORY"
{
    echo '```text'
    if [[ -s "$MIGRATION_FILES" ]]; then
        while IFS= read -r file; do echo "${file#$ROOT_DIR/}"; done < "$MIGRATION_FILES"
    else
        echo "No application migrations were discovered."
    fi
    echo '```'
} >> "$OUTPUT_FILE"

echo
echo "✅ Backend Data Protection snapshot created:"
echo "$OUTPUT_FILE"
echo
