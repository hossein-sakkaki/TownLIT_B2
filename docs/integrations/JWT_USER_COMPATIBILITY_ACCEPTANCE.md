# TownLIT — JWT/user compatibility acceptance gate

`docs/integrations/JWT_USER_COMPATIBILITY_ACCEPTANCE.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-07. Last Update by Hossein Sakkaki on 2026-11-07.

## Recommendation and scope

**BLOCKED for merge/release acceptance pending the decisions below.** Passing
synthetic regressions is not proof that production users will retain sessions.
This audit remains on existing Draft PR #7 and its existing feature branch.
No production dependency, enforcement flag, deployment or migration is changed.
PR #6 is read-only. No client, Accounting, Advancement or Office source changes.

This recommendation deliberately separates code correctness from release policy:
the canonical signed-ID adapter can be correct while a newly unconditional
current-account check, error contracts and client retry behavior remain an
unapproved compatibility delta. Do not loosen authentication to restore the old
permissive behavior. Obtain a concrete release decision before merging.

## Exact source references and attribution

Freshly fetched at the start of this gate:

| Reference | SHA | Meaning |
| --- | --- | --- |
| Backend `main` | `544b96b0b42434d9f52d672a6a418c21d9967eb6` | Source reference only; deployed production build is UNKNOWN |
| Security target | `00108e3eee45a67bdff8f80086875fb54af54211` | Existing security changes, not changes introduced by PR #7 |
| Expected/verified initial PR #7 | `7791af39d540d48e1987c05a6fc62bfd9f39ccb6` | The user-requested starting head |
| Audit PR #6 | `6710a1e990c1a84bfb9c0be49c02daf14cb8849a` | Read-only compatibility/design evidence |

The final tested and delivered SHAs are recorded in PR #7; a file cannot name
its own final commit. Main was inspected using Git objects, not by running its
tracked virtual environment or assuming it is production. Main pins Django
4.2.4 / DRF 3.14.0 / SimpleJWT 5.3.1 / PyJWT 2.8.0. The security baseline pins
Django 5.2.18 / DRF 3.18.3 / SimpleJWT 5.3.1 / PyJWT 2.8.0 and changes supporting
Django/asgiref/CORS/beat/typing/encrypted-field packages. The supported disposable
profile is the exact PR #6 full-manifest proposal: SimpleJWT 5.5.1, PyJWT 2.15.1,
cryptography 50.0.2, pyOpenSSL 26.4.0, cffi 2.1.1 and joserfc 1.8.0. Other direct
pins stay unchanged. Production `requirements.txt` remains untouched by PR #7.

Security-only JWT/authentication changes relative to main:

| Security source / commits | Actual delta already present before PR #7 |
| --- | --- |
| `apps/accounts/authentication.py`, `services/session_generation_policy.py`, `session_jwt.py`, `session_security.py`, `models/session_security.py`, `migrations/0105_user_auth_session_state.py` (`524dbffb`) | Per-user generation storage; all canonical issuance reads DB and adds `tl_sg`; optional REST/refresh/WS generation enforcement; missing state means zero, DB failure denies |
| `apps/accounts/views/auth_views.py` (`89a49ef6`, `7022ba4d`, `5a3b9c59`, `524dbffb`) | Atomic single-use 2FA, disclosure-resistant forgot-password responses, bounded dual-format reset readers, atomic reset consumption, gated password-driven revocation/login-required responses, all six JWT mint sites use generation-aware issuance |
| `services/two_factor_login.py`, `password_reset_tokens.py`, `password_session_policy.py` | Exact OTP shape and row lock/consume; random reset bearer with stored SHA-256 verifier; independent rollout gates |
| `views/token_obtain_views.py`, `townlit_b/urls.py` (`06cbb178`) | Generic `/api/token/` no longer bypasses 2FA/deleted/suspended/restricted-user issuance policy |
| `serializers/session_refresh.py`, REST/SIMPLE_JWT wiring in `townlit_b/settings.py` | Before PR #7: enforced generation lookup receives raw signed user-ID claim; flag-off delegates to upstream without extra current-user check |
| `apps/main/middleware.py`, `apps/core/websocket/consumer.py`, `access_auth.py`, `consumer_v2.py`, `routing.py`, `townlit_b/asgi.py` (`2aeb550a`, `524dbffb`) | Add V2 auth frame/registered device/origin/expiry/session checks; retain V1 URL-token route; V1 generation/type/account rechecks are gated; no PR #7 WS implementation changes |
| `apps/core/security/account_gate/service.py` | Optional fail-closed restricted-owner lookup for security-sensitive callers; middleware switches to generation-aware REST authentication |
| `apps/core/exceptions.py`, `townlit_b/security_logging.py`, ASGI logging (`fae27145`, `7022ba4d`) | Redact bearer paths and credentials; generic 500 response no longer exposes exception text |
| `accounts/tasks/maintenance_tasks.py` | Automatic abandoned-registration deletion now defaults disabled until explicit approval; no change by this PR |
| `apps/profiles/views/member.py` (`7022ba4d`) | Removes phone-verification OTP prints and email-address delivery error logs; the existing disclosure test checks no OTP output |
| Settings / other source | New flags default OFF; frontend reset URL, human CORS declarations and disabled Gateway boundary; Django 5 UTC compatibility fixes. Unrelated media/report changes exist in main→security and are not PR #7 changes |

PR #7's initial main→security-independent delta is exactly these five paths:

1. `apps/accounts/serializers/session_refresh.py`: signed-ID adapter, unconditional
   current-active-user/rule check, controlled failure mapping, parent delegation.
2. `apps/accounts/tests/test_refresh_user_id_compatibility.py`: 24 focused tests.
3. `scripts/ai_gateway_dependency_profile.py`: disposable full manifests only.
4. `.github/workflows/ai-gateway-b1.yml`: independent profile matrix and checks.
5. `docs/integrations/MILESTONE_03B_B11B1_REFRESH_HANDOFF.md`: evidence/recovery.

This gate adds process-separated transition tooling, focused availability tests,
expanded existing test execution, this matrix and header corrections to PR #7.
An existing WS mock gains `pk` to match a real user; its assertion is unchanged.
Its new files are `apps/accounts/tests/jwt_transition_worker.py`,
`apps/accounts/tests/test_jwt_user_acceptance.py`,
`scripts/check_jwt_user_transitions.py` and this acceptance document. It also
updates `tests/test_ws_access_auth.py` with a real-user-shaped fixture and
`apps/ai_gateway/tests/settings_backend.py` with the production-default phone
TTL for the previously unrun disclosure test. Existing security assertions stay
unchanged. No runtime authentication logic changed during this gate.
It does not reattribute security-branch runtime changes to PR #7.

## Authentication behavior impact matrix

`M` = inspected main source, not executed production behavior. `S` = security
baseline source. `P` = PR #7 final runtime. Library columns describe upstream
behavior in the selected full manifests; custom TownLIT policy still applies.
Evidence labels refer to the execution ledger below. Rows with source-only
findings are not silently upgraded to runtime acceptance.

| Behavior | Previous main (M) | Security baseline (S) | PR #7 (P) | SimpleJWT 5.3.1 | Proposed 5.5.1 | Classification | Test evidence / remaining acceptance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Email/password canonical login | Existing account/2FA flow; direct mint | Same flow; mint reads generation/table and adds claim | Same mint sites as S | Integer PK claim | String PK claim; low-level `for_user` only warns on inactive users | Claim/schema dependency changed in S; claim wire type changes with library | Issuance/legacy-login regressions; real deployed login, account flags and SSO pending |
| Generic password token endpoint | Upstream pair route can bypass application 2FA policy | Explicitly denies 2FA/deleted/suspended/restricted issuance | Same as S | Upstream does not know TownLIT 2FA | Same application responsibility | Intentional security tightening in S | `test_legacy_token_obtain_policy`; never call main's bypass backward-compatible behavior to preserve |
| Existing login 2FA | Validate code without atomic consumption | ASCII six digits, lock/recheck and consume once; account checks | Same as S | Token mint not a 2FA check | Same; inactive mint warning is not authorization | Intentional replay/malformed tightening in S | Six single-use tests; concurrent email delivery/device UX and deployed app acceptance pending |
| Refresh/current valid token | Parent rotation/blacklist | Same with flag OFF; strict generation when ON | Verify signed token, canonical ID/current user, optional generation, parent rotation | No refresh-time current-user rule in parent | Parent current-user lookup/rule | P adds current-user check even OFF; requires AUTH-01 decision | 66/24 existing tests plus availability tests; outage/capacity acceptance pending |
| Access-token verification | Upstream JWT user lookup/active check | Wrapper rechecks generation when enabled | Unchanged from S | Active users checked by JWTAuthentication | `CHECK_USER_IS_ACTIVE` defaults true; P refresh independently requires active | Optional generation tightening in S; no P access-source change | Access/revocation/WS tests; no production key/config inventory yet |
| Legacy integer / new string `user_id` | Integer issued for integer PK | Integer in 5.3.1; 5.5.1 string refresh fails enforcement | Accept only int or canonical ASCII positive signed-64-bit string; preserve wire type | Native integer issuance | Native canonical string issuance | Deliberate compatibility repair in P | Actual A–D, malformed/Unicode/Boolean/overflow/tamper tests; opaque-client source findings are not device acceptance |
| Missing / new `tl_sg` | Absent; no generation enforcement | All mint paths add current nonnegative integer; missing maps to zero | Same as S; no generation coercion | Copies custom claim | Copies custom claim | Deliberate S schema/issuance change; enforcement is optional | E/F; missing accepted while stored generation zero; rejected after first increment with enforcement ON |
| Token survival on upgrade / rollback | No extra claim/read | Old tokens survive only under applicable signature/expiry/account/generation policy | Both claim types supported across library rollback | Can consume canonical string through P | Can consume old integer through P | Bounded A–D compatibility, not universal survival | Same synthetic key/issuer settings and DB across processes; no key rotation, real ciphertext, old deployed build or SSO proof |
| Password change | Preserve session; no generation increment | Flag OFF preserves legacy contract; flag ON increments atomically, returns login_required and no JWT | Same as S | Does not implement app revocation | Same application responsibility | Intentional gated S behavior change | Password/session tests + cross-version F; flag ON with enforcement OFF refuses mutation (503) |
| Password reset / forgot password | Fernet bearer stored directly; response discloses bearer/account existence; reset returns JWT | Public uniform response, no bearer; dual reader; V2 issuance flag; atomic consume. Password flag OFF returns pair; ON requires full login incl. 2FA | Same as S | No application reset policy | No application reset policy | Intentional S tightening; response/token format rollout potentially incompatible | Disclosure/reset/single-use/revocation tests and F; real email links/frontend/app release coverage pending |
| Logout / session revocation | Blacklist submitted refresh; release device/push ownership; device event | Same logout method; password revocation separately generation based | Same as S | Sequential old refresh replay denied; outstanding creation can be deferred | Records rotated outstanding rows immediately | Logout is not automatic all-device/all-access revocation | Rotation/replay/G plus existing source; production device push/WS logout delivery pending |
| WS V1 auth / reconnect | Query-token middleware verifies HS256/expiry at handshake; existing owner gate | V1 retained; with enforcement ON require access type/account and generation at handshake/periodic recheck | Byte-unchanged from S | ORM accepts valid integer/string ID | Same through real resolved user PK | Intentional gated S tightening; refresh JWT as V1 credential no longer accepted when ON | Existing V1/V2 ASGI and access/session tests; real Web V1 stored-token reconnect risk remains |
| WS V2 auth / reconnect | Absent | Token-free URL, first auth frame, active account/device, origin, expiry timer/rechecks | Byte-unchanged from S | Access token required | Same | New S protocol, not backward-compatible route replacement | ASGI handshake/denial/expiry/device tests; iOS/Android reconnect loads token store but no observed WS-only token renewal |
| Soft deletion / reactivation | Canonical login can issue limited recovery tokens within window; action gates | Same policy | Active/generation-valid deleted user may refresh; original recovery/action checks remain | Parent allows active soft-deleted rows | Active rule alone does not encode domain recovery | Limited policy preserved; not a blanket authorization grant | Focused real user/permission/WS tests; complete recovery email/window/client UX not executed |
| Suspended / restricted owner | Existing action exceptions/owner gate; no general domain authorization from a JWT | Same domain gates, stricter WS paths | Limited refresh preserved for active current/generation-valid user; suspended logout/declared recovery exceptions untouched | No domain-flag policy | No domain-flag policy | Domain exceptions preserved, WS tightening belongs to S | Focused permission fixtures + existing WS gates; actual suspended/restricted clients pending |
| Inactive / physically deleted user | Access denies; 5.3.1 refresh may still mint without current user check | With OFF parent can mint; missing state alone is zero under ON | Unconditionally denies current inactive/missing user | Parent refresh lacks this denial | Active current-user check; missing lookup can otherwise raise | Intentional P tightening, including OFF; AUTH-01 unapproved release decision | Focused inactive/deleted/rule tests; source authorization is not deployed release approval |
| Expired/tampered tokens | JWT expiry/signature checks | Same crypto requirements; generation failures also deny | Verify first, never normalize unsigned data | Generic invalid/expired error text | Distinct expired-token error text | Denial maintained; exact errors not identical | Tamper/expiry tests; client status/detail assumptions reviewed statically only |
| DB/policy failure | Blacklist DB already required; user lookup failures not checked in 5.3.1 refresh | ON generation outage denies; OFF delegates errors | Additional user/blacklist read; failures become 401 with no credentials | Some parent DB/missing-user failures otherwise propagate | More parent user/outstanding DB work | Fail-closed maintained; outage error/availability contract changes in P | Enforcement-OFF outage + query-cost tests; no production load/failover proof; iOS/Web/Android can erase credentials after failures |
| Concurrent refresh / retry | Parent check/blacklist sequence, no atomic single-consumer guarantee | Same parent behavior | Parent semantics intentionally retained | Two consumers may verify before either blacklists | Same check/use race; new outstanding records do not serialize consumption | Existing race/lost-response incompatibility risk; not a new exactly-once guarantee | Controlled real-MySQL synchronized race/G; real device multi-request/multi-tab retry acceptance pending |

## PR #7 trusted-boundary review and explicit decisions

The only runtime adapter is `_verified_refresh_user_id` in the refresh serializer.
`RefreshToken(raw)` verifies signature, expiry, refresh type and blacklist before
normalization. Strings must be 1–19 ASCII decimal digits, no leading zero, and
in `1..9223372036854775807`; native integers must have exactly integer type.
Booleans, floats, signs, whitespace, Unicode digits, containers and overflow deny
before account/generation lookup. The signed payload is never rewritten.
`session_generation_matches` is byte-unchanged and receives resolved `user.pk`.
Current active/rule checks cannot be bypassed by generation enforcement being OFF.
Revoked/invalid input must produce no returned credentials; parent rotation and
per-profile blacklist/outstanding semantics remain authoritative.

### AUTH-01 — unconditional current-account policy (merge blocker)

This is an **intentional tightening**, not strict backward compatibility. Under
SimpleJWT 5.3.1 and enforcement OFF, S delegates directly to upstream, which can
refresh for an inactive or missing user. P always rejects these cases and also
canonicalizes IDs. Implementation authorization in the earlier repair request
is not evidence of release-owner approval for the OFF-mode compatibility delta.
No explicit deployed-client/operations approval was found in repository/PR
metadata. Keep this decision OPEN; do not quietly gate or remove the check to
reproduce the old permissive behavior.

### AUTH-02 — availability, errors and concurrency (release blocker)

The extra read is an availability dependency even with generation enforcement
OFF. Explicit query-cost tests compare valid parent and P refresh in each full
profile; database outage tests assert controlled denial with no credentials.
These tests cannot prove that added query volume, table-specific errors or
latency will never cause a broad outage. Blacklisting already required a working
DB, but that does not make the added reads or changed 401 mapping unchanged.
A failed late parent rotation can consume an old token; retry is not idempotent.

iOS clears tokens on refresh failure, including non-auth/network/5xx failures;
Android clears on 400/401/403; Web clears on 400/401 when the stored refresh still
matches the failed attempt. P's DB/policy 401 can therefore cause forced logout,
including while enforcement is OFF. Preserve fail-closed denial; separately
approve a transient-error contract, operational budgets and client handling.
The race characterization records what parent behavior actually does; passing
it does not approve two live descendant refresh chains as a security policy.

## Actual execution ledger

EXECUTION_PENDING — fill only from completed local/CI runs, never inferred from
same-version synthetic claim editing. Existing head 7791af39's completed run
42387580905 is prior evidence; new gate tests need their own exact SHA/results.

The real transition harness is `scripts/check_jwt_user_transitions.py` with
`apps/accounts/tests/jwt_transition_worker.py`. Each phase launches a fresh
interpreter from the baseline or supported full-manifest environment. Workers
clear inherited credentials, never load production settings, restrict outbound
I/O, use the fixed disposable test schema/socket/signing key, and assert real
accounts.0105 history. Only synthetic users/tokens exist in task-owned private
artifacts outside the repository; never commit/upload those token artifacts.

| Required case | Actually executed scenario | Result / evidence |
| --- | --- | --- |
| A | 5.3.1 issue → 5.3.1 refresh → 5.3.1 continued chain | PENDING |
| B | 5.3.1 issue → 5.5.1 refresh → 5.3.1 continued chain | PENDING |
| C | 5.5.1 issue → 5.5.1 refresh → 5.5.1 continued chain | PENDING |
| D | 5.5.1 issue → 5.3.1 refresh/controlled package rollback → 5.5.1 continued chain | PENDING |
| E | Real no-tl_sg tokens from each issuer, OFF and ON while zero; first revoke; OFF survives, ON denies | PENDING |
| F | Each A–D with generation increment, actual secure password change and V2 reset dispatch; both readers reject prior access/refresh/WS | PENDING |
| G | Consumed token replays rejected by both readers; rotated outstanding rows and user association match profile; blacklist survives transitions | PENDING |
| Concurrent refresh | Two real MySQL requests synchronized after parent blacklist checks; inspect distinct live descendants, then revoke/reject both across profiles | PENDING |

Test flags are overridden only inside synthetic workers/tests; no previously
disabled deployment flag is enabled. Signing-key fingerprint and applied
migration count must remain identical across phases. Library rollback retains
the forward-compatible schema, migration records and blacklist data. It does
not reverse accounts.0105, reset generations, flush blacklists or rotate keys.
5.5.1's blacklist migration 0013 alters model options, not stored token fields;
this bounded schema assumption must be re-reviewed for any other version.

## Current client source review, distinct from deployed acceptance

Freshly fetched default branch refs (checkout source remains unmodified):

| Client | Inspected SHA | Findings |
| --- | --- | --- |
| iOS | `95179ad944a1731dee9c22036bbfead5d08159d7` | AuthTokens stores String/String; refresh decodes String access/optional String refresh and saves rotation. URLSessionAPIClient is a final class with separate refresh calls in normal/upload 401 retry paths; no shared refresh flight/lock found. Its refresh catch clears tokens except CancellationError. Current password DTOs/repository support login_required; deployed app build unknown |
| Android | `cb59509327863128922eaf0cc99f2b8d1dc24176` | TLTokenRefresher synchronizes per instance, reuses a changed access token after waiting, saves rotated pair, clears credentials on 400/401/403 but retains on network/5xx. Session store reloads the shared token store; WS provider sees newly persisted access. Multiple refresher instances/processes are not a proven single flight |
| Web (`TownLIT_F`) | `614756be5f075850a22c1b3af8729b86d2d3544c` | authRefresh coalesces per-tab requests, saves rotation, clears only a still-current failed refresh on 400/401; no cross-tab lock. websocketManager stores this.token; RootAppShell captures a token in its connection effect; a refresh storage/cookie write alone is not a proven WS token update |

Repository-wide JWT decode searches and the inspected auth/storage/refresh
paths found no direct JWT user_id decoder or integer-claim requirement. Numeric
IDs in API user/notification/WS event DTOs are separate from signed JWT claims;
this repair does not change them. No build/device/browser acceptance was run.
Status-based error handling is not evidence that every message/detail change
is safe in every deployed client. No forced logout is intrinsically necessary
for an active generation-valid token with continuous signing settings, but
outages, retries, revoked sessions or client races can still force logout.

WS source findings: iOS and Android connect to V2 with an auth frame and reload
the stored access token when reconnecting; the inspected WS providers do not
perform HTTP refresh themselves. A socket-only session with an expired token
can keep reconnecting with an expired token unless another path renews it.
Web still uses the V1 URL-token route and reconnects using the captured token;
V1 must remain available until actual deployed Web migration is accepted.
Do not switch all clients to V2 or enable generation enforcement based on source
inspection alone. Device registration, origin/close-code handling, reconnect,
backgrounding and server expiry timing require real acceptance tests.

Evidence paths at the exact refs: iOS `Core/Networking/URLSessionAPIClient.swift`,
`Core/Storage/AuthTokens.swift`, `Core/Auth/Storage/AuthSessionStore.swift`,
`Core/Auth/Repository/AuthRepository.swift`, `Core/WebSocket/CentralWebSocketManager.swift`;
Android `core/network/.../auth/TLTokenRefresher.kt`, `core/auth/.../storage/AndroidAuthSessionStore.kt`,
`core/websocket/.../TLCentralWebSocketManager.kt`, `app/.../di/TLAppContainer.kt`;
Web `src/lib/authRefresh.ts`, `src/lib/websocketManager.ts`,
`src/utils/realtime/ws.ts`, `src/app/RootAppShell.tsx`.

## Required deployed-build evidence — no production secrets/access assumed

The repository's server/runbook notes describe installation, not an attested
running release. No inspected artifact identifies the exact current production
Backend revision or every deployed iOS/Web build. Do not substitute main's SHA.
Before release, the owner should supply redacted evidence through normal release
processes, without giving this audit real tokens, secret values or infrastructure
write access:

- Immutable deployment artifact/image digest plus build revision/commit and
  signed CI provenance, tied to the running service/process on every instance
  and background issuer, not just the checked-out directory.
- Package lock/SBOM or `pip show` version inventory from that build, deployed
  Python/OpenSSL versions, nonsecret issuer/audience/algorithm settings and key
  version/continuity identifiers. Never request signing keys or .env contents.
- Applied migration records/schema proof for accounts.0105 and third-party token
  blacklist migrations, with rollout/rollback owner and database backup evidence.
- Nonsecret actual flag values and per-instance consistency for generation,
  password security, reset-token issuance and WS routing/origin configuration.
- iOS App Store/TestFlight build numbers and Web asset/build revisions covering
  active users, plus SSO/older-client inventory and redacted acceptance receipts.

## Exact release dependency and safe future order

1. Approve the behavior decisions and identify the actual deployed build/client
   baseline. Preserve existing signing keys/settings and blacklist records unless
   a separate intentional revocation/key plan is approved.
2. Apply and verify **accounts.0105_user_auth_session_state after accounts.0104**
   before any security-branch process can mint tokens. This is required even with
   generation/password flags OFF: every `issue_session_refresh_token` call reads
   the table. Missing rows mean zero; a missing table is an error, not zero.
   Cover web workers, reset/2FA/choose-path issuers, generic token route and jobs.
   Run all normal reviewed release migrations; this note is not permission to
   apply production migrations in this task.
3. Deploy compatible readers/issuers consistently with existing flags retained.
   Keep V1 and both ID representations. Validate real login/2FA/refresh/logout,
   reset email/browser/app routing and account-recovery paths on representative
   deployed builds, including outage/retry/parallel requests and WS reconnect.
4. Only in a separately approved dependency rollout adopt the modern profile,
   after cross-version signing/schema/blacklist and real ciphertext/SSO/client
   acceptance. A rollback is package rollback with compatible readers and
   preserved database state; dropping the adapter while string tokens exist
   reintroduces the refresh failure.
5. Enable generation enforcement only after every issuance/auth/WS path, DB
   migration, client reconnect and emergency rollback is accepted. Missing legacy
   tl_sg is generation zero; accounts already incremented will lose old sessions
   when enforcement turns ON. Removing enforcement would revive still-valid old
   generations; this is not a safe automatic rollback.
6. Enable password-security V2 only with generation enforcement active and
   clients accepting login_required without JWT/user fields. Otherwise password
   mutations are deliberately refused. Enable V2 reset issuance only after every
   reset reader is compatible; old main readers cannot consume V2 reset bearers.
   Once V2 verifiers or revoked generations exist, rollback to old main can undo
   security guarantees or break reset links and requires a reviewed recovery plan.

No order above is executed in production by this audit. Merge acceptance remains
blocked until AUTH-01 has an explicit owner/security compatibility decision and
the deployed-build/client/operational evidence is accepted. A future dependency
upgrade or flag enablement requires its own release approval. Keep PR #7 Draft,
PR #6 unchanged, and both PRs unmerged here.
