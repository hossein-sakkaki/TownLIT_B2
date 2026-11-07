# TownLIT B1 — Security, quality and CI acceptance review

`docs/integrations/MILESTONE_03B_B1_ACCEPTANCE_REVIEW.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-06. Last Update by Hossein Sakkaki on 2026-11-06.

## Scope, source and acceptance rule

Reviewed the complete B1 implementation in existing branch
`feat/milestone-03b-ai-gateway-core`, Draft PR #4. Fresh remote head at start:
`3dcb715e7fa2ebe2525201e653bd07229f9b2248`; worktree clean. Approved base/target
remains `security/django-5.2-lts-20261022` at
`524dbffbb68ed7e1b74b72d6e088618ff73ae779`. Main remains
`544b96b0b42434d9f52d672a6a418c21d9967eb6`, the base ancestor (0/14 commits).
No new branch or PR, target change, merge or deployment is authorized/performed.

B1 acceptance means a **disabled development foundation** only. The required CI
job must pass at the current PR head before an owner-approved merge into the
security branch. Hosted run URL/head/result are recorded in PR #4 and the final
handoff; the workflow page always shows the current runs:
https://github.com/hossein-sakkaki/TownLIT_B2/actions/workflows/ai-gateway-b1.yml
The green status must never be interpreted as permission to enable any capability.

## Findings and corrections

| Finding | Evidence and correction |
| --- | --- |
| Malformed internal nonce context raised uncaught errors | Reproduced list/dict purpose and aware time-only timestamp as TypeError. Require exact string purpose and datetime timestamp before hashing/clock arithmetic; stable invalid_request, no reservation. |
| Malformed internal grant identifier raised validation exceptions | Reproduced invalid UUID strings/collections escaping revocation. Require a UUID value; stable denial before DB work. |
| Revocation could use a stale principal lock after grant reassignment | Deterministically reassigned the grant between initial principal lookup and locking. Previously revoked and audited under the old principal. Recheck locked grant ownership and deny/roll back if changed. No grant-provisioning endpoint was added. |
| Missing durable CI and inconsistent source headers/style | Added a focused read-only-token PR workflow, scoped header checker, pinned lint tool and formatting. Dates preserved; no runtime capability added. |

The three regressions failed before the fixes (one test failure and six failing
subcases/errors), then passed. They concern internal metadata primitives; no
public authentication bypass or domain access was found. New concurrent
conflicting-payload coverage requires one receipt/audit winner and one conflict;
the revocation race also asserts successful revocation completion explicitly.

## Focused review results

- Default deny: exact-True switch check; disabled paths do not parse credentials,
  bodies or touch DB. Enabled paths still hit UnavailableSecurity. No configurable
  authenticator/plugin can open the public surface. Unknown paths/methods deny.
- Identity/policy: no human-user FK or staff bypass; fixed immutable operation
  version and agent allowlist; Chloe denied even with a bad grant; exact current
  environment/org/principal-metadata scope and unexpired grant required. Loaded
  labels are rechecked against MySQL's case-insensitive collation. Organization
  UUIDs are provisional, not authoritative domain ownership or real record FKs.
- Transactions: principal -> organization -> grant -> receipt -> audit ordering;
  revocation shares principal serialization. Hashes avoid case-folded raw-key
  uniqueness. Nonce uniqueness and idempotency conflicts are real DB constraints;
  audit failure rolls back metadata. Nonces over-retain, receipts have no cleanup,
  and persistent audit is not cryptographically immutable. No durability/network
  exactly-once claim or hidden expiry/reuse behavior.
- HTTP boundaries: fixed /api/v1/ai-integrations/ include; no generic ORM endpoint,
  domain handler, JWT/user authenticator, CSRF exemption or auth middleware swap.
  CORS exclusion is only the machine prefix; human preflight remains compatible.
  Existing middleware may return its native 403 before a stub error response.
- Schema: 0001 remains six additive metadata tables, inactive defaults, scoped
  indexes/unconditional constraints and protective FKs; no domain migration or
  backfill. Formatting/header normalization does not change migration/model AST
  apart from import ordering. Full Backend tests assert accounts/0105 is applied
  and the migration executor has no pending leaf plan.
- Existing behavior: Accounting, Advancement, accounts authentication, ASGI,
  existing root human URLs and requirements are unchanged. The only edits to
  production settings/router in this review are source headers (AST unchanged).
  Synthetic Backend regressions include domain snapshots/zero domain SQL on
  denials, human JWT/session refusal and existing auth/route/socket validators.
- External access: runtime Gateway imports no domain, human-auth, JWT or outbound
  client module. Test settings never load .env/production settings/Firebase files;
  the runner clears inherited env and blocks Python network/subprocess calls
  except Django's exact local Git version probe. This is an accidental-I/O guard,
  not an adversarial sandbox; mysqlclient uses the fixed disposable Unix socket.

## Header and code-quality convention

Backend convention is the seven-line header used by
`apps/accounts/authentication.py`: exact path, TownLIT-Backend, separator, Created
by Hossein Sakkaki/date, Last Update by Hossein Sakkaki/date, separator. The Office
header checker also establishes the TownLIT ownership-attribution rule. B1 files
retain their existing 2026-11-06 creation date. Settings/router retain first-tracked
creation dates 2025-04-16 / 2025-05-26 verified from Git; updates use client date
2026-11-06. Actual implementation provenance remains in Git history. The checker
covers 29 B1 Python/YAML source files. Ruff 0.14.4 checks errors/import ordering
and formatting only within the new app/checker, without restyling existing Backend.

## CI design and reproducibility

`.github/workflows/ai-gateway-b1.yml` runs on pull_request updates targeting the
unchanged security branch, including Draft synchronizations; no pull_request_target.
It uses SHA-pinned checkout/setup-python, persist-credentials false, contents:read,
Ubuntu 24.04/Python 3.12, unchanged requirements plus pinned Ruff. It verifies the
exact approved remote security baseline and diff whitespace. No secrets context,
production credential, Firebase file, provider or financial service is required.

MySQL 8.4 image is digest-pinned to the previously tested image. It runs with
--network none, no ports, an explicitly bound sibling b1-mysql-socket directory,
empty synthetic local-only root password and fixed disposable database names.
No host/credential fallback or environment-driven DB overrides. Cleanup always
removes only the task-owned container. Test-only logging/durability settings do
not establish crash recovery. The job has a 45-minute timeout and cancellation.

CI commands match these local checks (use the installed isolated Python):

```
python scripts/check_ai_gateway_headers.py
ruff check --select E4,E7,E9,F,I apps/ai_gateway scripts/check_ai_gateway_headers.py
ruff format --check apps/ai_gateway scripts/check_ai_gateway_headers.py
python -m pip check
python -m apps.ai_gateway.tests.run mysql test apps.ai_gateway.tests --noinput -v 2
python -m apps.ai_gateway.tests.run core test apps.ai_gateway.tests --noinput -v 2
python -m apps.ai_gateway.tests.run mysql makemigrations ai_gateway --check --dry-run
python -m apps.ai_gateway.tests.run backend makemigrations ai_gateway --check --dry-run
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway --noinput
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway zero --noinput
python -m apps.ai_gateway.tests.run mysql migrate ai_gateway --noinput
python -m apps.ai_gateway.tests.run backend check
```

The workflow lists all nine selected Backend test modules explicitly (the same
66-test set as the original B1 handoff) and runs the entire real migration graph;
no migrations are disabled/faked. The 0105 regression now verifies the applied
record and no pending migration plan. Baseline-wide model drift is not asserted:
Gateway-only drift is checked under both isolated profiles. pip check validates
installed dependency metadata, **not vulnerability/advisory clearance**.

Local verified at this checkpoint: **28/28 Gateway MySQL**, SQLite **24 passed /
4 explicit MySQL skips**, 29 headers, scoped Ruff lint/format, both Gateway drift
checks and pip check pass. actionlint 1.7.7 validates the workflow (release archive
checksum verified). Fresh selected Backend regressions/hosted CI are being
completed; their actual results will be recorded before final acceptance.

## Remaining gates and limitations

No JWT/OAuth assertion or access-token verification, trusted-hop/mTLS, RFC 9421,
real certificate/key lifecycle, distributed quota enforcement, authoritative
organization/domain record binding, domain read/write handler or agent tool was
added. Cryptographic negative vectors are unrun because no verifier exists;
forged-header/transport tests demonstrate denial only. No production settings,
real TLS handshake, SSO, private storage ACL, historical ciphertext compatibility,
full Backend suite/load/crash/advisory audit is claimed. Existing CKEditor,
Requests/chardet and MySQL conditional-unique warnings remain baseline findings,
as do the earlier report/financial-authorization findings. None is silently fixed
or accepted for live use here. No CI repository branch-protection setting changed;
an owner must select the required B1 status check if enforcement is desired.

DR-03 real security profile and DR-04–15 remain open. Keep PR #4 Draft for owner
review. Any enablement, staging/production release, credential provisioning or
financial/legal authority requires separate approval. After this disabled core,
Office O1 remains an offline typed/fake client checkpoint, not live dispatch.
