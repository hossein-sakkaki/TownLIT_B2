# TownLIT B1 — Default-deny Gateway core

TownLIT-Backend · `docs/integrations/MILESTONE_03B_B1_HANDOFF.md`
Created by Codex on 2026-11-06. Last Update by Codex on 2026-11-06.

## Scope and baseline

Owner's B1 instruction authorizes isolated synthetic implementation/testing and a
Draft PR against `security/django-5.2-lts-20261022`, not main. Baseline freshly
verified: `524dbffbb68ed7e1b74b72d6e088618ff73ae779`. Main/merge base:
`544b96b0b42434d9f52d672a6a418c21d9967eb6`; full history, 0 main-only / 14
security-only commits, no merge commits in that range. Feature branch:
`feat/milestone-03b-ai-gateway-core`. Existing workspace TownLIT_B and Office
checkouts were clean and preserved. No Backend snapshot-only work was imported.

Office PR #3 remains Draft/unmerged. Authoritative documents read from its
`docs/milestone-03a-backend-audit` tip
`28f9ecf8684404d4b7cef856e8abfa841806a0ea`: AGENTS.md, audit, contract, plan,
decision register, baseline review and usage-safe checkpoint policy. Owner's
current instruction supersedes the documents' earlier no-implementation scope
for B1 only. DR-01/02 are authorized for this exact isolated baseline/scope;
DR-03 uses the safe metadata-only fallback. No real verifier is approved by B1.
All real read/mutation/release decisions DR-04–15 remain open.

## Endpoint checkpoint

Added isolated Django app and `/api/v1/ai-integrations/` denial stubs, including
`token/`, `capabilities/` and unknown paths. Global switch defaults false; true
still returns security unavailable. No credentials or tokens are issued or
verified; certificate/request-proof interfaces explicitly fail closed. No domain
operation handlers, human-user impersonation or authentication middleware changes.
Existing CSRF applies. Errors/log events exclude caller data and use server IDs.
Only code-reviewed metadata operation `gateway.capabilities` schema v1 is reserved;
it is not publicly executable. No domain operation is registered.

Executed with Python 3.12.14, Django 5.2.18, asgiref 3.12.1, sqlparse 0.4.4:

```
../b1-core-venv/bin/python -m django test apps.ai_gateway.tests.test_endpoints --settings=apps.ai_gateway.tests.settings -v 2
```

Result: **4 tests passed**, no database used. Covers disabled/enabled/malformed
switch, 6 paths × 7 methods × 4 switch values, forged certificate/identity headers,
security/audit exceptions, redacted errors, unavailable issuance and retained CSRF.
These denials do not prove cryptographic verification or end-to-end mTLS.
`git diff --check` and Python compile checks passed.

## Pending next checkpoint

Metadata models, migration and policy/replay/receipt implementation are being
validated separately; do not infer a pass from the endpoint checkpoint. Baseline
full-manifest installation initially lacked MySQL headers; dependency-only Debian
headers were extracted under `work/` without system installation. Full isolated
manifest install is in progress. Disposable MySQL 8.4 uses `--network none` and
synthetic empty-password local socket access only; no remote DB is configured.
MySQL transactions, migration reversal, accounts/0105, human authentication,
storage/encryption and full routing regression remain unverified at this checkpoint.

## Recovery and gates

Fetch the same feature branch and inspect the existing Draft PR before resuming;
never duplicate branches or PRs. PR head is the authoritative pushed SHA (a file
cannot contain its own commit hash). Preserve any local work. Complete metadata
security/migration tests and record exact outcomes here before review. Do not
merge, deploy, run production migrations, provision credentials or enable agents.
O1 next: a separate Office branch with typed offline Gateway client/fault-injection
transport only; no real network dispatch or tool registration.

## Metadata checkpoint (baseline regressions still running)

Implemented six additive metadata tables in `ai_gateway.0001_initial`:
ServicePrincipal, OfficeOrganizationBinding, OperationGrant, RequestNonce,
IdempotencyReceipt and AuditEvent. Defaults do not activate principals, bindings
or grants. There are no domain ownership changes/backfills. Organization UUIDs
are provisional references, **not verified Organization FKs or domain authority**.
The sole operation checks exact principal metadata scope; real module-specific
record bindings/selectors remain deferred. There is no wildcard scope.

`policy.py` intersects fixed operation/version, agent, environment, exact org IDs,
metadata record, token-scope-shaped internal input and current unexpired grant.
`VerifiedIdentity` is an internal test/policy value, not a verified HTTP identity.
No HTTP code constructs it from claims, headers, certificate strings or users.
Chloe and the nonregistered internal agents always deny. `replay.py` reserves
hashed nonces with a timestamp bound and DB uniqueness; `receipts.py` persists
strict v1 metadata envelope receipts and audit atomically, rechecking grants on
replay. These are internal primitives, not business POST/capabilities handlers.
No opaque reference can cause ORM model lookup or function invocation.

Lock order: principal -> organization -> grant -> receipt -> audit. Internal grant
revocation locks principal before grant/audit, so it serializes with receipt
reservation. No authority-changing provisioning endpoints exist. Nonce rows are
retained beyond their minimum 10-minute lifetime (no cleanup job); receipts have
no eviction/reuse path. Production retention/immutable audit export remain open.
Application audit is structured metadata, not a tamper-proof database. Disabled
HTTP attempts produce bounded log events without DB dependency; authoritative
persistent denial/rate controls must be reviewed before any live enablement.

Executed against disposable MySQL **8.4.13**, mysqlclient **2.2.6** and the full
pinned baseline Python environment:

```
../b1-venv/bin/python -m django test apps.ai_gateway.tests --settings=apps.ai_gateway.tests.settings_mysql -v 1
../b1-venv/bin/python -m apps.ai_gateway.tests.run mysql test apps.ai_gateway.tests -v 1
../b1-venv/bin/python -m django makemigrations ai_gateway --check --dry-run --settings=apps.ai_gateway.tests.settings_mysql
../b1-venv/bin/python -m django migrate ai_gateway --settings=apps.ai_gateway.tests.settings_mysql --noinput
../b1-venv/bin/python -m django migrate ai_gateway zero --settings=apps.ai_gateway.tests.settings_mysql --noinput
../b1-venv/bin/python -m django migrate ai_gateway --settings=apps.ai_gateway.tests.settings_mysql --noinput
```

Both MySQL test runs: **21 passed**, including two-connection nonce, same-key
receipt and revoke/reserve races. No concurrency claim is based on SQLite.
Migration drift check: no changes; apply/reverse/reapply all succeeded. A later
transport-denial case brings core discovery to **22 tests, 19 passed / 3 MySQL
cases explicitly skipped on SQLite**. MySQL rerun with that case remains pending.

Full baseline requirements installation succeeded; `pip check`: no broken
requirements. Initial toolchain failures (headers, then missing default clang)
were resolved by local extracted headers and `CC=gcc`; no dependency pins changed.
Baseline libraries include Django 5.2.18, DRF 3.18.3, asgiref 3.12.1,
django-celery-beat 2.8.1, django-cryptography-5 2.0.3, SimpleJWT 5.3.1,
PyJWT 2.8.0, cryptography 43.0.1. These existing crypto packages are **not an
approved Gateway crypto stack**. OAuth assertions/access JWT/mTLS/RFC 9421
verification, issuer/key/cert lifecycle and real token issuance are deferred.
No JWT/signature cryptography has been handwritten or selected without review.

The isolated runner clears inherited environment variables and prohibits Python
outbound network/subprocess execution except Django's exact local Git version
metadata probe. MySQL uses a fixed local socket and fixed disposable DB names.
Full Backend regression settings read app/middleware/auth declarations from AST
without executing production settings or loading .env. Broker/cache/channel/email
and media stores are local; there are no workers or real service credentials.
Normal production settings cannot be tested as configured because their Firebase
credential file is intentionally absent. No credential file was created.

Backend `check` under isolated settings completed with an existing CKEditor 4
unsupported/security warning, a Requests/chardet version warning and expected
missing-Firebase notice. These warnings are not remediated or approved by B1.
Full migration plan loaded, including accounts/0105 and third-party migrations.
Selected existing human-auth and new isolation regressions are still running;
results are not yet claimed. Production storage ACLs, old encrypted ciphertext,
full client/socket deployment behavior and advisory remediation remain unverified.
