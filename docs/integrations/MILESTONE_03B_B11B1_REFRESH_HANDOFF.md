# TownLIT B1.1B.1 — verified refresh user-ID compatibility

`docs/integrations/MILESTONE_03B_B11B1_REFRESH_HANDOFF.md` · TownLIT-Backend
Created by OpenAI Codex on 2026-11-07. Last Update by OpenAI Codex on 2026-11-07.

## Scope and provenance

Draft repair, no dependency adoption or production readiness approval. Separate
PR [#7](https://github.com/hossein-sakkaki/TownLIT_B2/pull/7) targets
`security/django-5.2-lts-20261022` from `fix/b11b-simplejwt-refresh-user-id`.
Fresh remote verification found security base
`00108e3eee45a67bdff8f80086875fb54af54211` and audit PR #6 head
`6710a1e990c1a84bfb9c0be49c02daf14cb8849a`. PR #6 was read only: its matrix,
failure evidence, upstream comparison and handoff informed this repair. No
cherry-pick, edit, merge or update of that audit branch/PR was performed.
No applicable Backend AGENTS.md was present.

The profile emitter derives the baseline and supported manifests from PR #6's
exact script at that immutable audit SHA. The diagnostic minimal profile is
intentionally omitted. Both generated manifests were compared byte-for-byte to
the audit script's output before testing. Production `requirements.txt` is
unchanged, including its existing advisory-affected baseline pins.

## Boundary and authorization

SimpleJWT 5.3.1 issues integer `user_id` claims for CustomUser's integer PK;
5.5.1 issues canonical decimal strings. The previous serializer passed the raw
verified claim to `session_generation_matches`, which correctly rejects strings.
The repair adapts this one trusted refresh boundary after `RefreshToken(raw)`
has verified signature, expiry, token type and blacklist status. It never uses
an unsigned decoded payload as identity.

The private adapter accepts only native positive integers or nonempty canonical
ASCII decimal strings in `1..9223372036854775807`. That bound follows the actual
`CustomUser.id` BigAutoField, checked by a test. Strings have at most 19 characters
before integer conversion. Booleans, floats, zero, signs, whitespace, leading
zeroes, exponent/hex notation, embedded nulls, Unicode digits, containers,
missing values and overflow all deny before user/generation lookup. This helper
has exactly one call site; it is not used by general identity, HTTP service or
WebSocket/session authentication. The shared generation validator is unchanged.

The normalized ID is local only. The signed payload and returned claim type
are not rewritten: old integer tokens and new string tokens keep their original
claim type during rotation and access-token derivation. Legacy absent `tl_sg`
means generation zero only until the first stored generation increment. Signed
malformed generation claims still deny; authoritative generation is uncached.

A small current-account guard accompanies the adapter. SimpleJWT 5.3.1's parent
refresh serializer does not check the current user, while 5.5.1 does. Both
profiles now require a current active user and the configured
`USER_AUTHENTICATION_RULE`. Missing accounts and DB/policy
failures deny with no returned credentials, including parent failures. This is
an intentional tightening of the old profile, necessary to avoid accepting
newly supported claims for missing/inactive accounts.
The guard applies even when generation enforcement is off; no enforcement
setting was changed. The existing 2FA issuance policy is untouched.

Domain account policy remains distinct. Canonical `AuthViewSet.login` deliberately
issues limited tokens for soft-deleted accounts within the recovery period;
`DenyIfDeletedOrSuspended` permits the declared reactivation/logout exceptions.
Existing restricted-owner constants also permit limited refresh. The adapter
preserves refresh for these active, current, generation-valid accounts while
leaving action gates and WebSocket denial unchanged. Refresh is not a blanket
authorization to call API operations. Existing action-specific permissions
remain responsible for those decisions. A real restricted Member fixture verifies
refresh can rotate while both WebSocket paths deny. Current account lookup,
generation lookup, blacklist and outstanding-token failures all fail closed.

The parent serializer still performs its own current-user checks and owns
rotation, outstanding-token insertion and blacklist behavior. No source changes
to shared generation logic, REST access auth, session auth, WebSocket auth,
Gateway runtime/HTTP denial, Accounting, Advancement, Office, iOS or Android.
No production dependency, settings, model or migration changes; no deployment,
production migration, merge, composer, mTLS or request signing.

## Inspected upstream differences

Installed 5.3.1 and 5.5.1 sources were compared directly:
[`serializers.py` 5.3.1](https://github.com/jazzband/djangorestframework-simplejwt/blob/v5.3.1/rest_framework_simplejwt/serializers.py),
[`serializers.py` 5.5.1](https://github.com/jazzband/djangorestframework-simplejwt/blob/v5.5.1/rest_framework_simplejwt/serializers.py),
[`tokens.py` 5.5.1](https://github.com/jazzband/djangorestframework-simplejwt/blob/v5.5.1/rest_framework_simplejwt/tokens.py),
[`authentication.py` 5.5.1](https://github.com/jazzband/djangorestframework-simplejwt/blob/v5.5.1/rest_framework_simplejwt/authentication.py).

- 5.5.1 stringifies `USER_ID_FIELD` in `for_user`. Inactive-user issuance still
  only warns there; callers must authorize issuance. No new issuance bypass.
- 5.5.1 refresh loads the current user and invokes the authentication rule.
  `CHECK_USER_IS_ACTIVE` defaults true. Its direct missing-user lookup can raise;
  the application boundary now maps unavailable accounts to controlled denial.
  The application guard also refuses inactive users independently of that flag.
- Both profiles blacklist the consumed refresh JTI when rotation and
  `BLACKLIST_AFTER_ROTATION` are enabled, then replace JTI/expiry/issued-at.
  Sequential replay of the consumed token must deny, and the rotated token must
  remain usable. The repair preserves configured rotation/blacklist settings.
- 5.5.1 additionally calls `refresh.outstand()` after rotation. A rotated token
  therefore has an outstanding row immediately; 5.3.1 may create that row only
  when later blacklisted. New blacklist/outstanding defaults attach the current
  user and creation time when available. Tests assert each actual profile's
  semantics, rather than forcing identical row counts or copying parent code.
- Blacklist verification uses JTI, and token construction verifies its signature
  before trusting payload identity. A DB failure during verification or rotation
  returns no credentials. Parent rotation is not made transactional here; a
  late failure can consume a token and require reauthentication.
- 5.5.1 excludes refresh `iat` when deriving access claims and distinguishes
  expired-token errors. Do not assume byte-identical token/error contracts.
  No blacklist-retention job or expiry policy was changed.

## Disposable profiles and measured results

Python 3.12.14 locally; MySQL image pinned by the existing workflow digest
`sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902`,
observed server 8.4.13. No network or published ports on the test DB container.
The existing isolated runner clears inherited credentials/environment, never
loads production settings/.env and prohibits outbound network and subprocesses.
Real Backend migrations are used, with no fake migration graph.

| Dependency | Baseline | Supported disposable candidate |
| --- | --- | --- |
| Django | 5.2.18 | 5.2.18 |
| SimpleJWT | 5.3.1 | 5.5.1 |
| PyJWT | 2.8.0 | 2.15.1 |
| cryptography | 43.0.1 | 50.0.2 |
| pyOpenSSL | 24.2.1 | 26.4.0 |
| cffi | 1.17.1 | 2.1.1 |
| joserfc | absent | 1.8.0 |
| django-cryptography-5 | 2.0.3 | 2.0.3 |
| Other direct production pins | unchanged | unchanged |

Full manifest SHA-256:
- Baseline (also production requirements): `d942524d2aa71a19dfe31bb94bba256883c7efe936b149970165a160944c6fda`.
- Supported: `a8ee6f02469d25ecd78dde0d32a96c37209118a6671cd6a86263525f5d471171`.

Local unchanged-source reproduction at tooling checkpoint
`88798d5792f43787ec29bbc1f926f9d040f09dbe` (refresh/session source byte-identical
to security base): baseline **66/66 PASS**, no skips, 24.282 seconds of test
execution after 800 real migrations; database cleanup passed.

Supported unchanged-source reproduction at that same checkpoint: **64 PASS /
2 FAIL**, no skips, 23.977 seconds of test execution after 801 real migrations.
The failures were exactly `test_current_refresh_still_rotates` and
`test_legacy_zero_refresh_accepted_before_first_revocation`, each **401 != 200**.
The complete test DB was retained only for subsequent disposable local checks.

Corrected source and tests at exact implementation SHA
`7542ab74c4c00807d8055de3f968f377b0843f6c`:

| Actual local check | Baseline 5.3.1 | Supported 5.5.1 |
| --- | --- | --- |
| Full manifest install / pip check | PASS | PASS |
| Unchanged selected Backend regressions | **66/66 PASS**, 27.618s | **66/66 PASS**, 23.489s |
| Focused signed refresh/account/policy tests | **24/24 PASS**, 5.244s | **24/24 PASS**, 6.195s |
| Gateway MySQL security and concurrency | **28/28 PASS** | **28/28 PASS** |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips | 24 PASS / 4 MySQL-only skips |
| Gateway drift (MySQL + Backend graph) | PASS | PASS |
| Gateway apply / zero / reapply | PASS | PASS |
| Isolated Backend check | PASS with existing warnings | PASS with existing warnings |

The corrected local Backend runs reused the fully migrated disposable test
schema with `--keepdb`, sequentially, while retaining independent full-manifest
venvs. No selected or focused Backend test skipped or changed an existing
expectation. New tests cover both claim types, canonical bounds, malformed and
tampered tokens, replay/rotation/blacklist/outstanding behavior, generation-zero
and revocation, inactive/physically deleted accounts, existing limited domain
policy, DB denial, and strict WebSocket/session behavior.

[Completed CI run 42385952101](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42385952101)
concluded **SUCCESS** at that exact implementation/test SHA. Both independent
profile jobs used fresh disposable MySQL containers and real Backend migration
graphs, with Python 3.12.16 / MySQL 8.4.13. Their logs identify CI merge ref
`8516b04393f215895127d40f7144516dfc8485e7` against the verified security base;
this is a test ref, not a merged PR.

| Actual completed CI check | Baseline | Supported |
| --- | --- | --- |
| Full manifest install / pip check | PASS | PASS |
| Selected Backend regressions | **66/66 PASS**, 33.304s | **66/66 PASS**, 25.151s |
| Focused refresh tests | **24/24 PASS**, 7.064s | **24/24 PASS**, 5.284s |
| Gateway MySQL | **28/28 PASS** | **28/28 PASS** |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips | 24 PASS / 4 MySQL-only skips |
| Gateway drift, reversible migration, Backend check | PASS with existing warnings | PASS with existing warnings |
| Profile job / disposable DB cleanup | SUCCESS / PASS | SUCCESS / PASS |

Exact jobs:
[baseline 128443230437](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42385952101/job/128443230437),
[supported 128443230900](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42385952101/job/128443230900).
The existing separate isolated ES256 profile also passed **11/11**:
[job 128443230695](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42385952101/job/128443230695).
No selected or focused Backend tests skipped. Completed job steps and decoded
logs were inspected directly. Earlier canceled/intermediate runs are not the
final two-profile evidence. Local task-owned MySQL cleanup also completed; no
task database container remains.

The final handoff commit adds documentation only after the tested implementation;
its delivery SHA is recorded in PR #7. Source, tests, workflow and manifests are
unchanged from the successful implementation SHA above. A documentation push
may trigger another CI run; it is not substituted for this completed evidence.

Each dependency profile has a fresh venv; CI jobs have independent MySQL
containers. Local DB checks run sequentially against a task-owned disposable
server because a second Docker instance exhausted the small workspace disk.
Only task-owned pip/apt caches and a redundant clone were removed to recover
space. No test passed as a result of that failed infrastructure attempt; the
attempt could not connect and is excluded from successful results.

Existing warnings remain visible: unsupported CKEditor 4.22.1, Requests dependency
mismatch, MySQL conditional-unique constraint warnings and absent synthetic
Firebase project configuration. Reused Backend test-schema setup also reports a
`posts` model-state warning. It was reproduced with unchanged source at
`88798d57` using the existing current-access test against the same cached schema;
that control passes. Explicit isolated `makemigrations posts --check --dry-run`
on both unchanged and corrected source reports no changes (exit 0). No Posts
source or migration was modified. These warnings were not suppressed or
release-approved.
Four Gateway concurrency tests skip only on SQLite and run on MySQL. None of the
66 selected Backend expectations is changed, waived or skipped.

## Read-only client inspection and required release decision

Current default-branch heads inspected without changing client repositories:

| Client | Exact inspected SHA | Relevant source |
| --- | --- | --- |
| iOS | `ad550bf1684f875f93497fd178b683642a662a2b` | `TownLIT/Core/Storage/AuthTokens.swift`, `Core/Networking/URLSessionAPIClient.swift:732`, `Core/Auth/Models/AuthDTOs.swift:296` |
| Android | `c19f32385a4d570324588770a26e89f407e77e39` | `core/network/src/main/kotlin/com/townlit/android/core/network/auth/TLTokenRefresher.kt`, `core/auth/src/main/kotlin/com/townlit/android/core/auth/model/AuthFlowDtos.kt` |
| Web (`TownLIT_F`) | `614756be5f075850a22c1b3af8729b86d2d3544c` | `src/lib/authRefresh.ts`, `src/redux/auth/authSlice.ts`, `src/utils/security/privateIntegrationGate.ts` |

Auth/storage/refresh and repository-wide JWT/decode searches found no JWT
`user_id` claim decoding in these heads. iOS stores access/refresh as String and
its refresh DTO contains String access and optional String refresh. Android
stores tokens as strings, serializes the refresh unchanged and persists the
rotated pair. Web treats tokens as opaque strings and persists rotation with
single-flight handling. Numeric identity fields (iOS Int64, Android Long, Web
number) are in API response/user models and remain unchanged by this repair.

Source evidence:
[iOS refresher](https://github.com/hossein-sakkaki/TownLIT_iOS/blob/ad550bf1684f875f93497fd178b683642a662a2b/TownLIT/Core/Networking/URLSessionAPIClient.swift#L732),
[Android refresher](https://github.com/hossein-sakkaki/TownLIT_Android/blob/c19f32385a4d570324588770a26e89f407e77e39/core/network/src/main/kotlin/com/townlit/android/core/network/auth/TLTokenRefresher.kt),
[Web refresher](https://github.com/hossein-sakkaki/TownLIT_F/blob/614756be5f075850a22c1b3af8729b86d2d3544c/src/lib/authRefresh.ts).

No claim-type client patch is indicated by those inspected paths. The release
owner must still approve string JWT identity claims for **new issuance**, retain
numeric API identity fields, inventory deployed/older clients and SSO consumers,
and exercise real login/refresh/replay/logout and reconnect flows with both
claim types. This is static source inspection, not full client compatibility.
No mobile/Web builds, device/browser acceptance, deployed-version inventory or
SSO end-to-end tests were performed. No client repository was modified.

## Recovery and review gates

Keep this PR Draft and unmerged until owner/security review. Do not adopt the
supported dependency profile as a side effect of this repair or use the
advisory-affected minimal profile as a workaround. Selected tests do not approve
a full Backend upgrade, historical ciphertext compatibility, real-client/SSO
behavior, production capacity or production readiness.

Fetch the same feature branch, inspect local status and verify the remote head
and PR head agree. Preserve local work; use a new worktree for recovery rather
than reset/rebase. Verify the security target before applying further changes.
Generate each full manifest with
`python scripts/ai_gateway_dependency_profile.py baseline|supported` into a
task-owned path, create a new venv per profile, install and run `pip check`.
Never overlay candidate packages on production requirements.

The checked-in workflow gives the exact pinned MySQL startup, Gateway SQLite/
MySQL, real/reversible migration, Backend check, unchanged 66-test selection and
focused refresh-test commands. A job may retain **its own disposable** test DB
between the two Backend test commands with `--keepdb`; the always-run container
cleanup removes it. Do not reuse or point the runner at production credentials.

If a later deployment rollback is authorized, retain this dual-claim adapter
through a dependency rollback: removing it while string tokens exist recreates
the refresh failure. Rotation preserves legacy claim types; do not assume all
old claims disappear simply after one refresh. Coordinate session invalidation
and client reauthentication if a separate reviewed rollback requires them.
DB/policy outages must continue to deny; do not disable session enforcement or
bypass account checks to restore availability. Restore service health and allow
reauthentication where a failed rotation already consumed the old token.
