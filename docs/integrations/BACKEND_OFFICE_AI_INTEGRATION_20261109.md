# Backend / Office AI integration candidate — 2026-11-09

Draft review candidate only. No deployment, merge, credential provisioning or
Gateway activation. This document is the current integration handoff; adjacent
B1/B1.1/refresh documents retain historical source evidence.

## Provenance and preserved baseline

Branch: `integration/backend-office-ai-20261109`.
PR target: `checkpoint/backend-before-codex-auth-20261109`.
Exact parent baseline: `c51ad810ecef6fd4d6ffff6bc660c44676cfe9f4`.

Selectively copied the Gateway B1/B1.1A foundation from security branch
`00108e3eee45a67bdff8f80086875fb54af54211` and the focused refresh adapter,
failure classification and test assets from Draft PR #7
`8cf2b79fea30b9ae07a4b2f31ed77b86fe6f6b34`. Neither source branch was merged.
No work from the separate dependency/identity milestone branch was imported.

All pre-existing migrations, including accounts.0105 through accounts.0114,
data-protection implementation, business features, production dependency
manifests, REST authentication classes, shared session-generation validation and
WebSocket V2 runtime are unchanged from the checkpoint. The only existing
runtime files changed are the refresh serializer, the legacy token-issuance
email alias, the API URL include and Gateway-specific settings.
Existing rollout flags retain their definitions and
defaults. The new Gateway migration adds isolated metadata tables only.

## Resulting contract

- `/api/token/refresh/` accepts signed positive BigAutoField integer IDs and
  canonical ASCII decimal-string IDs without rewriting signed payloads.
  Upstream rotation/blacklisting remains in place. Numeric API identities do
  not change. Strict generation validation remains shared and unchanged.
- `/api/token/` again accepts the legacy `email` request key alongside the
  checkpoint's concrete `username` key. It passes the alias through the existing
  manager's protected natural-key lookup and preserves parent validation and
  username precedence. No plaintext email column/query is restored; account and
  2FA issuance checks are unchanged. This fixes a checkpoint regression exposed
  by the retained legacy-issuance test, which returned 400 after USERNAME_FIELD
  changed to username. Denial tests now require 401 through both input keys, so
  a missing-field 400 cannot masquerade as security-policy coverage.
- Known invalid/expired/revoked refresh credentials return
  `401 / token_not_valid`; unavailable dependencies return sanitized
  `503 / refresh_unavailable`; unexpected failures return sanitized
  `500 / refresh_failed`. Explicit permission denial remains sanitized 403.
  Request validation and throttling retain DRF's 400 and 429 behavior.
  Failures issue no credentials or exception details and perform no retry.
- **AUTH-01 remains OPEN.** PR #7's current-active-account check also runs with
  generation enforcement OFF. Retaining that proposed behavior is not owner
  approval of its tightening relative to SimpleJWT 5.3.1. This integration
  neither removes/gates the check nor resolves the rollout policy.
- Gateway defaults OFF. Even with its flag ON, all public routes call
  `UnavailableSecurity` and deny. Human sessions/JWTs and synthetic service
  tokens cannot authorize it. Browser CORS exclusion is Gateway-specific.
- Metadata policy retains current principal, organization, grant, environment,
  scope, agent and expiry checks; transactional replay/idempotency receipts and
  audit records remain metadata-only. No business handler, outbound action,
  callback dispatch, token issuer or Office credentials are connected.
- The ES256 verifier is synthetic-only, explicitly invoked and isolated from
  HTTP identity composition. Its separate test manifest is not a production
  dependency overlay. The supported full test profile likewise changes no
  production pins.

## Client contract review

Read-only source review used iOS `integration/ios-auth-20261109` at
`fec9899766e1e0737e1a899b91fbb9e57421fcd3` and Web
`integration/web-auth-20261109` at
`415f46056965252a8e36bcbe0ef4b691fa6d38f8`.
Both send refresh strings to the existing root `/api/token/refresh/` path,
consume access strings and optional rotated refresh strings, and distinguish
verified `401/token_not_valid` rejection from ambiguous/transient failures.
Their retention and explicit retry contracts match this server candidate.
No client checkout was changed. Backend WS V2 routes, frames, close codes,
device/account gates and runtime files are unchanged. Static review and
synthetic Backend tests do not establish device/browser runtime acceptance.

Read-only Office contract/decision review used `AI_GATEWAY_V1_CONTRACT.md`
and `MILESTONE_03B_DECISION_REGISTER.md` at
`5cb67e3cf87d838ceab672d4d0b270cb8cd9cf06`. The preserved foundation is
consistent with their default-deny boundary, not their complete proposed
authentication or business-operation contract. No Office file was changed.

## Isolated verification

Tests run in Codex Cloud using Python 3.12.14, independent complete baseline
and supported dependency environments, in-memory SQLite and a newly initialized
task-owned MariaDB 11.8.6 server through a fixed Unix socket with networking
disabled. No Docker commands or existing services/databases were used.
The test runner clears inherited environment, supplies only public synthetic
data-protection keys, avoids production settings/.env, and rejects outbound
Python network/subprocess I/O. Transition workers use the same synthetic keys
and the checkpoint's blind-index lookup instead of the removed email column.

CI retains the earlier disposable MySQL 8.4 matrix and is retargeted to the exact
checkpoint; local MariaDB evidence must not be labeled MySQL 8.4 evidence.

| Completed Codex Cloud check | Baseline / SimpleJWT 5.3.1 | Supported / SimpleJWT 5.5.1 |
| --- | --- | --- |
| Selected Backend regressions, including encrypted identity/0114 and legacy alias | 69 PASS | 69 PASS |
| Signed refresh ID compatibility | 24 PASS | 24 PASS |
| Expanded account, WS V2 and refresh failure contract | 73 PASS | 73 PASS |
| Checkpoint field protection, encrypted-only email and natural keys | 23 PASS | 23 PASS |
| Gateway / task-owned MariaDB | 28 PASS | 28 PASS |
| Gateway / in-memory SQLite | 24 PASS, 4 database-specific skips | 24 PASS, 4 database-specific skips |
| accounts/ai_gateway migration drift; Backend system check | PASS, existing warnings | PASS, existing warnings |
| Independent full dependency manifest / pip check | PASS | PASS |

Each profile passed 189 Backend cases without skips. The isolated ES256 profile
passed 11/11 cases and pip check. Gateway apply/reverse/reapply, scoped Ruff
lint/format, source headers and whitespace checks passed. All 782 pre-existing
migration files were compared byte for byte with the checkpoint. The completed
synthetic Backend schema contains 810 applied migration records, including real
accounts.0114, with no pending migration plan. No fake migrations were used.

The real-library transition matrix passed **37 separate-interpreter phases /
246 actions**, covering issuance, refresh, upgrade/rollback, legacy generations,
password/session revocation, blacklist persistence, concurrent descendants and
cross-version reset-link consumption/replay. Every phase retained the same
synthetic signing fingerprint and 810 migration records. Both profiles still
produced two live children in the controlled concurrent-refresh characterization;
subsequent generation revocation denied them through both readers. This is
evidence of the existing race, not an exactly-once guarantee.

Observed warnings remain CKEditor 4 support/security, the existing Requests
dependency mismatch, absent synthetic Firebase configuration and eight
conditional-unique constraints unsupported by MariaDB/MySQL. Expected injected
failure logs accompany passing denial/redaction tests. These are not silently
suppressed or approved for production.

The clean MariaDB replay stopped at unchanged `posts.0091` with error 1072:
dropping `content_id` while its composite index/unique constraint still exists.
This was reproduced on a separate empty copy of the table. For focused test
execution only, those two obsolete indexes were removed from the task-owned
test table that 0091 immediately deletes, then the unchanged migration graph
was resumed. No migration was edited or fake-applied. Consequently a passing
focused test suite here is not evidence of a clean full MariaDB replay, and a
clean MySQL 8.4 replay of this candidate remains a separate validation limit.
The original migration matches the checkpoint byte for byte; it is outside the
Gateway/refresh change scope.

After verification, the task-owned server was stopped and its data/socket plus
raw synthetic token artifacts were removed. Existing services and checkouts
were untouched.

## Material limits before a secure Office connection

1. Gateway remains a disabled foundation. Trusted principal/key lifecycle,
   authoritative Office-to-Backend organization binding, certificate/mTLS and
   proxy trust, request proof/signing, current policy composition and production
   dependency approval remain prerequisites. The synthetic verifier lacks the
   complete contract's `cnf`/`policy_version`; metadata receipts do not make
   future domain side effects idempotent.
2. AUTH-01 needs owner policy approval before release. AUTH-02 production and
   deployed-client acceptance remains open. Refresh rotation is not exactly-once:
   concurrent requests can create multiple descendants; a consumed parent with
   a lost response or late failure may require login/2FA. No blacklist rollback,
   generation reset or transparent retry recovery is provided.
3. Current client branches retain credentials on transient failures, but real
   iOS/Web/WS reconnect, cross-tab/concurrent rotation and deployed-artifact
   acceptance remain unverified. No live Office, historical production
   ciphertext, capacity/failover, SSO or production migration check is claimed.
   Existing password/reset/session rollout flags remain unchanged.

## Temporary iMac worktree review

Run only when the owner chooses to review locally. Use the existing remote name
if it differs from `origin`; choose a new, unused worktree path. These commands
do not alter the existing checkout's files or apply migrations:

```sh
git fetch origin integration/backend-office-ai-20261109
git rev-parse origin/integration/backend-office-ai-20261109
git worktree add --detach ../TownLIT_B2-office-ai-review origin/integration/backend-office-ai-20261109
git -C ../TownLIT_B2-office-ai-review diff --stat c51ad810ecef6fd4d6ffff6bc660c44676cfe9f4 HEAD
```

Compare the fetched SHA with the Draft PR delivery receipt before reviewing.
Do not use a production .env, start services, migrate an existing database,
merge, deploy or enable flags as part of this review.
