# TownLIT B1 — Default-deny Secure Gateway core

`docs/integrations/MILESTONE_03B_B1_HANDOFF.md` · TownLIT-Backend
Created by Codex on 2026-11-06. Last Update by Codex on 2026-11-06.

## Status and repository evidence

Restricted B1 implementation only. **Every public Gateway capability remains
unavailable, including when its global kill switch is enabled.** No domain
handler, real token issuer, credential provisioning, agent, external action,
merge or deployment is enabled. Synthetic test success is not release approval.

- Repository: `hossein-sakkaki/TownLIT_B2`.
- Verified base/PR target: `security/django-5.2-lts-20261022` at
  `524dbffbb68ed7e1b74b72d6e088618ff73ae779`.
- Main/merge base: `544b96b0b42434d9f52d672a6a418c21d9967eb6`; full history,
  0 main-only / 14 security-only commits, no merge commits in that range.
- Feature: `feat/milestone-03b-ai-gateway-core`;
  [Draft PR #4](https://github.com/hossein-sakkaki/TownLIT_B2/pull/4), remain unmerged.
- Checkpoints: `0659a076773cee1af4af68527197989fec5060f0` endpoints;
  `f976ce76ef8af93915ef32a045a1f64a64e27d19` metadata/transactions;
  `9c5d0528b84063bfb44e53374c1f9b94d8981a94` MySQL labels;
  `6afc25bbf88a398b1264cfa84894c41814bad542` CORS/test fixtures.
  The PR's head is the final pushed SHA; this file cannot contain its own commit hash.
- GitHub app reported push permission and published the branch/checkpoints; local
  fetched head matches. Existing `TownLIT_B` and Office working trees were clean
  and preserved. No snapshot-only Backend edits were imported or overwritten.

Office PR #3 remains Draft/unmerged. Read AGENTS.md, audit, contract, plan,
decision register, baseline review and usage-safe policy from authoritative
`docs/milestone-03a-backend-audit` at
`28f9ecf8684404d4b7cef856e8abfa841806a0ea`. The current owner instruction
supersedes their earlier documentation-only authorization for this B1 scope.
No Office runtime or research-branch source was changed.

Reviewed the full 14-commit consequences without repeating the domain audit:
Django/dependency upgrade, UTC compatibility, Celery guards/task registration,
legacy/V2 socket changes, redaction, reset/2FA/session authentication, STORAGES,
accounts/0105, and broader media changes. The security baseline is not a minimal
auth-only series. In particular, token issuance requires accounts/0105 even with
session-generation enforcement off. Existing rollout/reset/storage flags were
not changed. Gateway has no dependency on human tokens or auth-user privileges.

## Implemented modules and schema

`apps/ai_gateway/` contains:

| Modules | Behavior |
| --- | --- |
| apps, urls, views | Isolated `/api/v1/ai-integrations/` denial stubs, including token/capabilities/unknown paths and methods. |
| security | Dedicated identity value and credential/access-token/certificate/request-proof Protocols; concrete verification and issuance always unavailable. A constructed VerifiedIdentity is an internal fixture/policy input, never verified HTTP identity. |
| registry, policy | Immutable code-reviewed `gateway.capabilities` schema-v1 metadata registry; current principal/agent/environment/org/exact metadata-record/scope/grant intersection. Chloe and all unregistered agents deny. No dispatch functions or dynamic model invocation. |
| validation | Bounded strict metadata envelope, duplicate/unknown key rejection, exact types/UUID, versioned canonical digest. No domain JSON schema accepted. |
| replay | Timestamp bounds, hashed nonce reservation and unconditional database uniqueness. |
| receipts | Atomic metadata receipt/audit, same-key digest conflict, current authorization on replay, serialized grant revocation. No business operation or caller callback. |
| audit, errors | Fixed redacted codes, server UUIDs, bounded denial logs; persistent metadata audit excludes arbitrary body/headers/URLs/secrets. |
| tests | Isolated SQLite/MySQL profiles, environment-clearing/outbound-I/O-blocking runner, core and selected full-Backend regressions. |

Production integration changes only register the app, add the new API include,
add `AI_GATEWAY_ENABLED` default false, and exclude only the machine prefix from
browser CORS/preflight. Existing human CORS, CSRF, middleware, REST/business/root
URLs and WebSocket sources remain unchanged. Native middleware CSRF rejection
can return its normal 403 before the Gateway error envelope. No broad auth bypass.

`apps/ai_gateway/migrations/0001_initial.py` creates six metadata tables only:
ServicePrincipal, OfficeOrganizationBinding, OperationGrant, RequestNonce,
IdempotencyReceipt and AuditEvent. Principals/bindings/grants default inactive;
expiry is required for grants. Scoped unconditional uniqueness/indexes and
protective metadata FKs apply. No RunPython/backfill or Accounting/Advancement
ownership/schema change, ledger, opportunity store or domain record grant exists.

Organization UUIDs are **provisional references, not verified Organization FKs or
domain ownership**. The sole record scope is the exact principal metadata record.
Real module-specific organization/record/FK selectors remain unavailable. No
collection wildcard, creator/name inference or automatic legacy-record grant.

Writers lock principal -> organization -> grant -> receipt -> audit. Grant
revocation locks principal before grant/audit and serializes with reservations.
Exact loaded labels are rechecked to prevent MySQL case-insensitive collation
from broadening policy. Nonces are retained beyond their 10-minute minimum;
no cleanup exists. Receipts have no eviction/reuse path. Audit is ordinary
protected application metadata, not cryptographically immutable storage. Disabled
HTTP requests use bounded log events without a DB dependency; live denial-audit
retention/export and shared rate enforcement remain gated.

## Actual validation

Environment: Python 3.12.14; complete unchanged baseline requirements installed;
`pip check` passed. Django 5.2.18, DRF 3.18.3, asgiref 3.12.1,
django-celery-beat 2.8.1, django-cryptography-5 2.0.3, SimpleJWT 5.3.1,
PyJWT 2.8.0, cryptography 43.0.1, mysqlclient 2.2.6. Existing crypto packages
are **not an approved Gateway verifier stack**. No new JOSE/signature library
or handwritten JWT/HTTP-signature cryptography was added.

MySQL 8.4.13, image `mysql:8.4` digest
`sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902`.
Only a task-owned `--network none` container and fixed sibling
`b1-mysql-socket/mysqld.sock` were used. DBs are `townlit_b1_disposable`,
`test_townlit_b1_gateway`, `test_townlit_b1_disposable`; no configurable remote
host/credential fallback. Headers were extracted locally for mysqlclient and
`CC=gcc` used after the missing-header/default-clang build failures. Pins and
system packages were not changed. Binary logging was off; after initial core
transaction checks, disposable `innodb_flush_log_at_trx_commit=2` reduced schema
setup cost. No crash-durability claim.

From Backend root, using the isolated environment's Python:

```
python -m apps.ai_gateway.tests.run mysql test apps.ai_gateway.tests -v 1
python -m apps.ai_gateway.tests.run core test apps.ai_gateway.tests -v 1
python -m apps.ai_gateway.tests.run mysql makemigrations ai_gateway --check --dry-run
python -m apps.ai_gateway.tests.run backend makemigrations ai_gateway --check --dry-run
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway --noinput
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway zero --noinput
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway --noinput
python -m apps.ai_gateway.tests.run backend check
```

Core: **24/24 MySQL tests passed**, including two-connection nonce/same-key/revoke
races. SQLite: **21 passed / 3 explicit MySQL skips**. Migration drift: none.
Gateway migration apply/reverse/reapply succeeded on MySQL. Full Backend graph,
including accounts/0105 and third-party migrations, applied in disposable MySQL.

Full selected regression command:

```
python -m apps.ai_gateway.tests.run backend test apps.ai_gateway.tests.backend_regression apps.accounts.tests.test_session_jwt_issuance apps.accounts.tests.test_session_generation_enforcement apps.accounts.tests.test_session_security_foundation apps.accounts.tests.test_legacy_token_obtain_policy apps.accounts.tests.test_password_reset_token_v2 apps.accounts.tests.test_password_session_revocation apps.accounts.tests.test_two_factor_login_single_use apps.accounts.tests.test_backend_exception_redaction --noinput --keepdb -v 1
```

**66/66 selected Backend tests passed** (61 existing authentication/security tests
and 5 new integration-boundary tests), after all **800 migration records** applied.
The new tests verify human JWT and superuser sessions cannot authorize Gateway,
accounts/0105-backed generation revocation, unchanged human/business/socket route
definitions, current-library synthetic encrypted-field round trip and local
storage, plus before/after snapshots of every Accounting/Advancement model and
zero domain SQL during denied requests. Only an artificial Advancement fixture
was created for the snapshot; all data was disposable. These are not complete
Backend or production-client regression tests.

The first full 66-test attempt had 52 passes, 4 failures and 10 errors: the new
fixture assigned read-only is_staff (five errors), and isolated expiry defaults
were missing (OTP/reset errors/failures). Corrected the fixture and test settings
only; existing authentication source was not modified. Final results above
supersede that failed attempt; it is not hidden or counted as a pass.

Normal production settings were not executed successfully because the required
Firebase credential file is intentionally absent. Isolated settings load only
literal/bounded app/middleware/REST/JWT declarations from source AST, never .env;
synthetic secrets, in-memory email/broker/cache/channel/media, no workers. The
runner clears inherited environment and rejects Python outbound network and
subprocesses except Django's exact local Git version probe. No mTLS fixture is
represented as a real TLS connection.

Observed baseline warnings: unsupported CKEditor 4, Requests/chardet version
compatibility, expected missing Firebase, and MySQL models.W036 for existing
conditional unique constraints in accounts/boundaries/main/profiles/sanctuary.
Those conditional constraints are not enforced by MySQL. B1 has no conditional
uniqueness. These findings are recorded, not remediated or approved by B1.
`git diff --check`, compilation and changed-runtime import/scope checks passed.

## Security evidence and deferred gates

| Required cases | Evidence / honest limit |
| --- | --- |
| Disabled, unknown identity/operation, missing configuration/grants | Deny tests, including complete synthetic metadata configuration and all public methods. |
| Agent/org/record isolation; Chloe | Canonical labels, invented organizations, exact principal metadata record; deliberately bad Chloe grant. Real domain selectors never exist/enabled. |
| JWT issuer/audience/alg/expiry/signature | **Not implemented/tested as verification.** All credentials meet an unavailable boundary. |
| Certificate/proxy trust | Forged headers cannot authorize; actual certificate-chain/trusted-hop/mTLS verification deferred. |
| Body/method/path/header tampering | Public denial tests only; RFC 9421 cryptographic detection deferred. |
| Nonces/idempotency/revocation | Real MySQL uniqueness, conflict, two-connection races and current grant checks; no domain/network exactly-once claim. |
| Security/audit store failure | Fail closed; metadata receipt/revocation audit failure rolls back. |
| Domain and human compatibility | 66 selected Backend checks passed, including unchanged domain snapshots/zero domain SQL and JWT/session/router/0105 checks; no production/full-suite claim. |
| Schema | Core reversible migration and full disposable baseline/0105 graph; no production migration. |

Deferred: OAuth/private_key_jwt, short-lived audience-bound ES256 service access
tokens, real issuer/key/cert registry and rotation, authenticated TLS terminator,
RFC 9421 library/profile, distributed rate limits, authoritative organization and
domain FK bindings, real capabilities, proposals/drafts/human authority/files,
events and all agent tools. These require reviewed versions/synthetic vectors
and later gates; **the public Gateway cannot enable them by configuration**.

Owner instruction authorizes DR-01/02 for this exact isolated baseline/scope;
DR-03 uses the metadata-only fallback and its real crypto profile remains open.
DR-04–15 remain open: authoritative ownership, principal lifecycle, issuer/proxy/
key custody, existing report/finance findings, security stores, human review,
privacy/files/retention/residency, recovery, events and deployment. No release
approval follows from this work. Old encrypted ciphertext compatibility, private
storage ACLs, real clients/SSO/ingress, full socket handshakes/load/security-advisory
remediation and the complete Backend test suite remain unverified.

## Recovery and next checkpoint

Fetch and reuse this feature branch/PR; compare remote SHA and worktree before
resuming. Preserve local work and do not duplicate branches, PRs or migrations.
The next **separate** Office O1 checkpoint is a typed Gateway client with offline
fake transport, bounded retries/same-key lost-ack recovery and Chloe-denial tests.
Keep network dispatch, credential use, agent tools and domain operations off.
Staging/production access, credential provisioning, releases and any final
financial/legal authority require separate owner decisions. Do not merge/deploy.
