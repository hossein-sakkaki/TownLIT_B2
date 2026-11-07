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
