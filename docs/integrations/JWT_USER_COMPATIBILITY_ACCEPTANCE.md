> Historical source-branch evidence. For this checkpoint-based integration, use
> [BACKEND_OFFICE_AI_INTEGRATION_20261109.md](BACKEND_OFFICE_AI_INTEGRATION_20261109.md).
> Prior branch heads, commands, acceptance counts and readiness statements below
> describe their original work, not this integration candidate.

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
unchanged. No runtime authentication logic changed during the initial gate at
349450c2. The subsequent AUTH-02 remediation below changes only the refresh
boundary and its directly required tests/CI coverage and documentation.
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
| DB/policy failure | Blacklist DB already required; user lookup failures not checked in 5.3.1 refresh | ON generation outage denies; OFF delegates errors | AUTH-02: typed dependency failures 503; unexpected failures 500; known invalid/account denial remains 401/403; never return credentials on failure | Some parent DB/missing-user failures otherwise propagate | More parent user/outstanding DB work | Deliberate refresh error-contract repair; fail-closed remains | Fault tests/ledger below; iOS and Web startup can still erase credentials on transient failures; operational/client acceptance OPEN |
| Concurrent refresh / retry | Parent check/blacklist sequence, no atomic single-consumer guarantee | Same parent behavior | Parent semantics intentionally retained | Two consumers may verify before either blacklists | Same check/use race; new outstanding records do not serialize consumption | Existing race/lost-response incompatibility risk; not a new exactly-once guarantee | Controlled real-MySQL synchronized race/G; real device multi-request/multi-tab retry acceptance pending |

## PR #7 trusted-boundary review and explicit decisions

The only identity adapter is `_verified_refresh_user_id` in the refresh serializer.
AUTH-02 adds `_RefreshTokenPreflight`: upstream decoding verifies the signature,
then `Token.verify` checks expiry, required claims and refresh type before any
database work. Only then is the signed user ID normalized. The boundary next
checks the authoritative blacklist before user/generation lookup or parent
delegation; the unmodified parent rechecks the blacklist before rotation. This
ordering denies known malformed/type/ID inputs even when blacklist DB access is
unavailable. It does not skip a blacklist decision or add another decoding pass.
Strings must be 1–19 ASCII decimal digits, no leading zero, and
in `1..9223372036854775807`; native integers must have exactly integer type.
Booleans, floats, signs, whitespace, Unicode digits, containers and overflow deny
before account/generation lookup. The signed payload is never rewritten.
`session_generation_matches` is byte-unchanged and receives resolved `user.pk`.
Current active/rule checks cannot be bypassed by generation enforcement being OFF.
Sequential invalid/revoked requests return no credentials in the executed
checks. An atomic no-new-credentials guarantee during concurrent blacklist
consumption is **not established**: the synchronized parent-library race returns
two live children. Parent rotation and per-profile blacklist/outstanding
semantics are preserved, rather than silently replaced with a new consumption
protocol that could log out existing concurrent clients. AUTH-02 therefore stays
open; this audit does not certify exactly-once refresh or retry idempotency.

### AUTH-01 — unconditional current-account policy (merge blocker)

This is an **intentional tightening**, not strict backward compatibility. Under
SimpleJWT 5.3.1 and enforcement OFF, S delegates directly to upstream, which can
refresh for an inactive or missing user. P always rejects these cases and also
canonicalizes IDs. Implementation authorization in the earlier repair request
is not evidence of release-owner approval for the OFF-mode compatibility delta.
No explicit deployed-client/operations approval was found in repository/PR
metadata. Keep this decision OPEN; do not quietly gate or remove the check to
reproduce the old permissive behavior.

### AUTH-02 — server error classification repaired; client/release acceptance OPEN

The extra read is an availability dependency even with generation enforcement
OFF. Explicit query-cost tests compare valid parent and P refresh in each full
profile; database outage tests assert controlled denial with no credentials.
These tests cannot prove that added query volume, table-specific errors or
latency will never cause a broad outage. Blacklisting already required a working
DB, but that does not make the added reads or status contract unchanged.
A failed late parent rotation can consume an old token; retry is not idempotent.

At initial checkpoint 349450c2, broad exception handling incorrectly mapped
DB/policy failures to 401. AUTH-02 removes that credential classification:
recognized unavailable-dependency exceptions return sanitized 503; unexpected
failures return sanitized 500. No failure response returns access/refresh data.
AUTH-01's active-account check remains unconditional and unapproved for release.

iOS still clears tokens on non-cancelled refresh failures, including 503;
Android's refresher preserves them on 5xx/network errors. Web's central helper
preserves them on 5xx/network errors, but RootAppShell startup's broad catch
still deletes them. Server remediation alone does not preserve every deployed
client's tokens. Preserve fail-closed denial; complete the separate client fixes,
operational budgets and deployed-build acceptance below.
The race characterization records what parent behavior actually does; passing
it does not approve two live descendant refresh chains as a security policy.

## AUTH-02 exact refresh error contract

The classification is scoped to `SessionGenerationTokenRefreshSerializer` under
the existing HS256/signing settings. No REST access, WebSocket, login, password,
2FA, shared validator, settings, production dependency or consumption protocol
is changed. Missing/empty request fields and malformed JSON continue to use
DRF's request-validation 400; they are not retryable dependency failures.
View-level throttling remains 429. This serializer adds neither a retry loop nor
a Retry-After promise; 503 is not evidence that replay is safe or will succeed.

Inspected installed upstream source in both complete environments: the parent
5.3.1 refresh path reparses/rechecks the blacklist, builds access in memory,
gets/creates the old outstanding row and blacklist row, then changes JTI/expiry/
issued-at and serializes the rotated refresh. Parent 5.5.1 also reads the current
user before access creation and during blacklist/outstand operations, and calls
outstand for the new refresh after consuming the old one. These parent methods
are not copied or replaced here. TokenRefreshView catches TokenError and maps
it to InvalidToken; typed DRF 503/500 exceptions pass to the existing TownLIT
exception handler. Exceptions raised before serializer.validate (JSON/field
validation, middleware, throttling) and transport failures after view return
remain outside this remediation's mapping.

| Boundary outcome | HTTP / machine code | Credential/state semantics |
| --- | --- | --- |
| Invalid signature, expired JWT, invalid encoding, wrong token type, missing required JWT claim, invalid canonical user ID; invalid enforced generation shape | 401 / `token_not_valid` | Known-invalid checks occur before DB access; no user lookup/rotation |
| Readable blacklist says consumed/blacklisted; readable generation says revoked | 401 / `token_not_valid` | Never return credentials; retain blacklist/generation |
| Missing/inactive user or false authentication rule, including parent's current-user denial/deletion race | 401 / `token_not_valid` | AUTH-01 unchanged; no relaxation when generation flag is OFF |
| Explicit DRF PermissionDenied from the account rule | 403 / existing DRF permission-denial shape | Sanitized fixed account message; does not become 503 |
| Django OperationalError / InterfaceError; built-in ConnectionError / TimeoutError anywhere inside refresh validation/parent delegation | 503 / `refresh_unavailable` | Authoritative decision unavailable; deny without credentials; no retry, blacklist deletion or generation reset |
| Other unexpected errors, including programming/schema/integrity failures | 500 / `refresh_failed` | Fail closed; no internal exception details/tokens in the response |

OperationalError/InterfaceError denote dependency unavailability, not a guarantee
that the cause is temporary or retries will repair it. ProgrammingError and
IntegrityError are deliberately not made retryable 503s. No blanket DatabaseError
or Exception→503 mapping exists. A token whose stored revocation state cannot be
read is **not known valid**: it receives 503 without credentials; after recovery,
the same revoked/blacklisted token receives 401. It is impossible to attest that
stored state during an outage, and this contract never assumes generation zero
or an empty blacklist in that situation.

Typed DRF APIException subclasses carry only fixed public strings. The existing
TownLIT DRF handler wraps them as these exact JSON bodies:

```json
{"message":"Session validation temporarily unavailable. Please try again later.","error":{"detail":"Session validation temporarily unavailable. Please try again later.","code":"refresh_unavailable"}}
```

```json
{"message":"Session validation failed.","error":{"detail":"Session validation failed.","code":"refresh_failed"}}
```

Token-invalid messages retain the upstream/application denial contract rather
than exposing exception text. Explicit account exceptions are replaced by the
fixed `Account access is unavailable.` message. No new catch logs raw exceptions,
request payloads, SQL, JWTs or traceback details. No change to the shared exception
handler is needed. HTTP transport/proxy failures after the response leaves this
boundary cannot be detected or reclassified by the serializer.

### Failure stage and retry limits

| Injected failure stage | Expected result | Later use of submitted token |
| --- | --- | --- |
| Backend acquisition before signature verification | Typed connection/timeout: 503; unexpected: 500; no normalization or credentials | Can succeed after recovery if still valid/unconsumed |
| First blacklist read / parent's repeated blacklist read | 503, no consumption | Can succeed after recovery; known-invalid local shape still returns 401 before the failed read |
| Current-user read / generation read | 503; no credentials; no generation fallback | Valid unconsumed token may retry; revoked token still denied once state is readable |
| Parent's current-user read (5.5.1 only) | 503, no consumption | Can succeed after recovery; 5.3.1 has no such parent lookup |
| Before parent's blacklist write; old outstanding-row get/create or blacklist-row get/create | 503, no successful consumption in the injected case | Tested later retry succeeds; ambiguous real commit failures are not promised recoverable |
| After real blacklist write but before method returns / JTI rotation failure | 503, no returned credentials; consumed parent retained | Retry receives 401; reauthentication may be unavoidable |
| New rotated outstanding-row creation (5.5.1 only) | 503 after parent consumption; no returned pair | Retry receives 401; 5.3.1 does not call outstand during rotation |
| Successful rotation response lost before client persists it | Server completed 200; client sees no acknowledgement/new pair | Old-token retry receives 401; server cannot transparently recover a lost child credential |

Fault injection exercises real MySQL token state while failing specific calls.
A separate transaction test closes/reopens the real connection and injects the
driver connection failure. This is not a physical database failover/load test.
Current production settings use autocommit, without ATOMIC_REQUESTS; no new
transaction wraps rotation. Do not undo committed blacklists to make retries
work. An ambiguous commit, lost response or local persistence failure can still
require full login/2FA. No exactly-once, idempotent refresh, grace period, replay
cache, new refresh family or guaranteed transparent recovery is introduced.

## AUTH-02 verification checkpoint

Runtime/test/workflow checkpoint:
`7a5f4ed023efbde3e835d11e206da16f7b997d72`. Subsequent changes are acceptance
Markdown only; the final delivered SHA is recorded in PR #7 separately.

| Completed AUTH-02 local verification | Baseline full profile (5.3.1) | Supported full profile (5.5.1) |
| --- | --- | --- |
| Selected Backend regressions, unchanged assertions | **66/66 PASS**, 23.324s | **66/66 PASS**, 21.880s |
| Existing 82 auth/WS + 15 new failure-contract cases | **97/97 PASS**, 14.551s | **97/97 PASS**, 13.810s |
| Gateway MySQL | **28/28 PASS**, 0.371s | **28/28 PASS**, 0.411s |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips, 0.181s | 24 PASS / 4 MySQL-only skips, 0.187s |
| Full-manifest pip check, scoped lint/format/headers/whitespace | PASS | PASS |
| Accounts/Gateway drift, Gateway apply/zero/reapply, Backend check | PASS with existing warnings | PASS with existing warnings |
| Real A–G plus H transitions after remediation | **37 phases / 246 actions PASS**, separate interpreters for both profiles | Same shared experiment |

No selected or expanded Backend case skipped. The 97 count includes the
previous 82; it is not 97 new cases. The new 15 cases test exact 503/500 JSON,
401/403 denial, redaction, no returned credentials, real connection reopening,
blacklist/generation retention, and consumed-token/lost-ack limitations. The
profile-specific parent lookup and new-outstanding failure execute under 5.5.1;
5.3.1 cases explicitly prove those parent operations are absent, not skipped.
Both profiles also retain the measured two-extra-read assertion on valid OFF-mode
refresh. No new broad exception→503 rule or retry protocol was required.

Local full migrations applied accounts.0105 (800 baseline records), then the
supported profile's blacklist 0013. The repeated 37-phase experiment retained
**801 migration records and one signing fingerprint** throughout. Both races
again returned two distinct live children/two 200s; generation revocation then
denied every child in both readers. This remains characterization, not security
approval. The pinned MySQL 8.4.13 container had network none, no published ports
and synthetic tmpfs storage, and was removed after completed local verification.
Independent complete manifests have the same hashes recorded in the initial
gate below; production requirements remain unchanged.

### Completed AUTH-02 CI

[Run 42421070773](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42421070773)
completed **SUCCESS** at source/test head
`7a5f4ed023efbde3e835d11e206da16f7b997d72`, using proposed merge test ref
`396aaf0929f490c0383ce7b295842bac3c7cb5c2` against unchanged security target
`00108e3eee45a67bdff8f80086875fb54af54211`. This is not an actual PR merge.
Finished job metadata and decoded logs were inspected. Both jobs freshly
installed independent complete manifests and used separate isolated MySQL
containers; observed Python 3.12.16 / MySQL 8.4.13.

| Completed AUTH-02 CI check | [Baseline job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42421070773/job/128549404343) | [Supported job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42421070773/job/128549403353) |
| --- | --- | --- |
| Selected Backend regressions | **66/66 PASS**, 25.657s | **66/66 PASS**, 20.582s |
| Focused refresh compatibility | **24/24 PASS**, 5.583s | **24/24 PASS**, 4.207s |
| Expanded account/WS plus new failure-contract cases | **73/73 PASS**, 10.179s | **73/73 PASS**, 7.964s |
| Gateway MySQL | **28/28 PASS**, 0.224s | **28/28 PASS**, 0.202s |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips, 0.107s | 24 PASS / 4 MySQL-only skips, 0.087s |
| Full profiles/pip, headers/lint, migration drift/reversibility, Backend check, container cleanup | PASS | PASS |
| Cross-version A–G plus H | Per-job step intentionally absent here; both interpreters execute in supported job | **37 phases / 246 actions PASS**, additional independent baseline full environment |

The 24+73 split is the same **97** acceptance cases run locally, including the
prior 82 and 15 new fault-contract cases. No Backend case was skipped. The only
test skips are the four MySQL-only Gateway cases on SQLite; all execute on MySQL.
The cross-version step is intentionally conditional on the supported CI job,
not an omitted transition scenario. The separate [isolated ES256 job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42421070773/job/128549403502)
passed **11/11**, 0.043s. All three jobs and their cleanup steps succeeded.
Subsequent documentation-only changes do not alter the tested runtime, tests,
manifests or workflow. Historical run 42392588702 below remains initial-gate
evidence, not the evidence for this changed error boundary.

Server classification remediation is verified within these profiles. **AUTH-02
release acceptance remains OPEN** for actual client token retention, transient
error UI/backoff, production capacity/failover, lost acknowledgements and
concurrency policy. AUTH-01 is still an explicit separate owner decision;
CLIENT-01 Android password V2 and deployed-build/client acceptance remain open.
PR #7 stays Draft and **BLOCKED**. No deployment, production migration, flag or
dependency change follows from these passes.

The changed outage assertions intentionally require the newly authorized 503
contract, and additionally require sanitized code/body, no credentials, preserved
blacklist/generation state and safe later retry where consumption did not occur.
Existing invalid/revoked/inactive/malformed 401 assertions remain strict. The
blacklist-outage fixture now expects signed-ID preflight before the unavailable
read so known malformed input cannot be mislabeled as an outage. No security
denial is converted to successful authentication to obtain a pass.

## Actual execution ledger — initial mandatory gate (historical)

The gate's source/test checkpoint is
`b9b84ce367071bd861f3d59282d08b7afdc78ab3`. All source/test logic in the completed
local runs below matches that checkpoint; only the acceptance documentation is
updated afterward. Existing head 7791af39's run 42387580905 remains prior repair
evidence, not a substitute for the expanded gate.

| Actual completed local check | Baseline full profile | Supported full profile |
| --- | --- | --- |
| Full-manifest identity / pip check | PASS / SimpleJWT 5.3.1 | PASS / SimpleJWT 5.5.1 |
| Unchanged selected regressions | **66/66 PASS**, 24.088s | **66/66 PASS**, 24.209s |
| Expanded authentication acceptance | **82/82 PASS**, 12.554s | **82/82 PASS**, 12.197s |
| Gateway MySQL | **28/28 PASS**, no skips | **28/28 PASS**, no skips |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips | 24 PASS / 4 MySQL-only skips |
| Gateway + accounts migration drift, Gateway apply/zero/reapply, Backend check | PASS with existing warnings | PASS with existing warnings |
| Real separate-interpreter transitions | **37 phases / 246 actions PASS**, both libraries; one signing fingerprint, 801 unchanged migration records | Same shared experiment |

The 82-test suite includes the existing 24 refresh cases, five new availability/
canonical-login/2FA-challenge/logout cases, seven disclosure cases, ten account/
organization contract cases and 36 existing WS/access/session/logging/UTC cases.
The five new cases prove canonical login's numeric API user ID is preserved,
2FA challenge returns no credentials, logout is idempotent and token-scoped,
enforcement-OFF lookup outages deny without credentials, and the serializer adds
exactly **two SQL reads** over upstream for a valid OFF-mode refresh (one current
user lookup plus one blacklist verification). No production load conclusion
follows from that count. Logout leaves sibling refresh/access credentials valid
unless a separate generation/device policy revokes them.

The MySQL server is the workflow's pinned 8.4 image (observed 8.4.13), network
NONE, no published ports, synthetic schema only. Python 3.12.14 locally; both
venvs contain complete independently resolved manifests. The real full Backend
graph applied accounts.0105; the supported reader applied blacklist 0013. Local
subsequent suites retain that disposable schema, without fake migrations.
Generated baseline manifest SHA-256:
`d942524d2aa71a19dfe31bb94bba256883c7efe936b149970165a160944c6fda`;
supported:
`a8ee6f02469d25ecd78dde0d32a96c37209118a6671cd6a86263525f5d471171`.

### Completed CI gate

[Run 42392588702](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42392588702)
completed **SUCCESS** for source/test head
`b9b84ce367071bd861f3d59282d08b7afdc78ab3`. GitHub tested proposed merge ref
`6d279394d599cbf3e783f55c13233a1a3eb7fc17` against security target
`00108e3eee45a67bdff8f80086875fb54af54211`; this is a CI ref, not an actual PR
merge. Each full-profile job installed its own complete environment and started
its own network-isolated disposable MySQL. Observed Python 3.12.16 / MySQL 8.4.13.

| Completed CI check | [Baseline job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42392588702/job/128463158615) | [Supported job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42392588702/job/128463158428) |
| --- | --- | --- |
| Selected Backend regressions | **66/66 PASS**, 25.764s | **66/66 PASS**, 22.292s |
| Focused refresh compatibility | **24/24 PASS**, 5.349s | **24/24 PASS**, 4.702s |
| Additional account/WS acceptance | **58/58 PASS**, 6.070s | **58/58 PASS**, 5.725s |
| Gateway MySQL / SQLite | 28 PASS / 24 PASS + 4 MySQL-only skips | 28 PASS / 24 PASS + 4 MySQL-only skips |
| Full manifests, pip check, headers/lint, migration drift/reversibility, Backend system check | PASS | PASS |
| Real cross-version A–G plus H | Executed using an additional independent baseline full environment in the supported job | **37 phases / 246 actions PASS**, including the characterized concurrent-refresh race |
| Disposable-container cleanup | PASS | PASS |

The separate [isolated ES256 job](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42392588702/job/128463158565)
also passed **11/11**, 0.042s. The 24+58 split is the same 82-case expanded
acceptance set reported locally, not 82 additional tests beyond that set.
Earlier canceled checkpoints are not final gate passes. Final documentation-only
changes do not change the tested runtime, tests, manifests or workflow; the final
delivered SHA is recorded separately in PR #7. The task-owned local MySQL
container was also removed after successful verification.

Test setup findings were fixed without weakening assertions: the old WS mock
lacked `pk`; the isolated test settings lacked the production-default phone TTL.
The first process worker attempted the default AMQP broker and was stopped by
the no-network audit hook before external I/O. Its one synthetic fixture was
removed from the disposable schema, the worker was bound to the configured
in-memory test Celery app, and a fresh complete 37-phase run passed. Those
failed setup attempts are not counted as passing scenarios. Queue delivery,
real email/SMS/push and background trust work are not accepted by this harness.

Existing CKEditor, Requests dependency, MySQL conditional-unique and empty
Firebase test-configuration warnings remain visible. Reused Backend schema
setup prints a known Posts model-state warning; explicit drift checks remain
scoped to accounts/Gateway here, and no Posts source or migrations were edited.
No selected or expanded Backend test skipped. Only four Gateway cases skip on
SQLite; all four execute successfully on MySQL.

Not executed: main's old runtime, production/deployed-client acceptance,
historical production ciphertext, live SSO/email/SMS/push/queue delivery,
production load/failover, multi-instance stress, or concurrent login/2FA/password
mutation stress. The controlled two-request refresh race is the concurrency
experiment actually performed; it does not stand in for those scenarios.

The real transition harness is `scripts/check_jwt_user_transitions.py` with
`apps/accounts/tests/jwt_transition_worker.py`. Each phase launches a fresh
interpreter from the baseline or supported full-manifest environment. Workers
clear inherited credentials, never load production settings, restrict outbound
I/O, use the fixed disposable test schema/socket/signing key, and assert real
accounts.0105 history. Only synthetic users/tokens exist in task-owned private
artifacts outside the repository; never commit/upload those token artifacts.

| Required case | Actually executed scenario | Result / evidence |
| --- | --- | --- |
| A | 5.3.1 issue → 5.3.1 refresh → 5.3.1 continued chain | **PASS**, native integer claim retained |
| B | 5.3.1 issue → 5.5.1 refresh → 5.3.1 continued chain | **PASS**, real old-issued integer claim retained |
| C | 5.5.1 issue → 5.5.1 refresh → 5.5.1 continued chain | **PASS**, native string claim retained |
| D | 5.5.1 issue → 5.3.1 refresh/controlled package rollback → 5.5.1 continued chain | **PASS**, real new-issued string claim accepted after rollback |
| E | Real no-tl_sg tokens from each issuer, OFF and ON while zero; first revoke; OFF survives, ON denies | **PASS** under both libraries; test-only flag overrides |
| F | Each A–D with generation increment, actual secure password change and V2 reset dispatch; both readers reject prior access/refresh/WS | **PASS**; fresh rotated tokens were not already blacklisted and access failure code was session_revoked |
| G | Consumed token replays rejected by both readers; rotated outstanding rows and user association match profile; blacklist survives transitions | **PASS**; 5.3.1 defers rotated outstanding row, 5.5.1 records it immediately |
| Concurrent refresh | Two real MySQL requests synchronized after parent blacklist checks; inspect distinct live descendants, then revoke/reject both across profiles | **OBSERVED** two 200 replies/two valid children in each profile; revocation then denies all children in both readers |
| H (extra recovery check) | Eight legacy Fernet/V2 reset links issued/consumed across A–D; both readers retry consumed links and reject old JWTs | **PASS**; resets return login_required without JWT, replay is 404 |

Test flags are overridden only inside synthetic workers/tests; no previously
disabled deployment flag is enabled. Signing-key fingerprint and applied
migration count must remain identical across phases. Library rollback retains
the forward-compatible schema, migration records and blacklist data. It does
not reverse accounts.0105, reset generations, flush blacklists or rotate keys.
5.5.1's blacklist migration 0013 alters model options, not stored token fields;
this bounded schema assumption must be re-reviewed for any other version.
Reset-link consumption matches a stored verifier/bearer; H is not proof of
historical production encrypted-field/ciphertext compatibility.

## Current client source review, distinct from deployed acceptance

Freshly fetched default branch refs (checkout source remains unmodified):

| Client | Inspected SHA | Findings |
| --- | --- | --- |
| iOS | `95179ad944a1731dee9c22036bbfead5d08159d7` | AuthTokens stores String/String; refresh decodes String access/optional String refresh and saves rotation. URLSessionAPIClient is a final class with separate refresh calls in normal/upload 401 retry paths; no shared refresh flight/lock found. Its refresh catch clears tokens except CancellationError. Current password DTOs/repository support login_required; deployed app build unknown |
| Android | `cb59509327863128922eaf0cc99f2b8d1dc24176` | TLTokenRefresher synchronizes per instance, reuses a changed access token after waiting, saves rotated pair, clears credentials on 400/401/403 but retains on network/5xx. Session store reloads the shared token store; WS provider sees newly persisted access. Multiple refresher instances/processes are not a proven single flight. Current reset DTO still requires refresh/access/is_member; password change ignores login_required (CLIENT-01) |
| Web (`TownLIT_F`) | `614756be5f075850a22c1b3af8729b86d2d3544c` | authRefresh coalesces per-tab requests, saves rotation, clears only a still-current failed refresh on 400/401; no cross-tab lock. websocketManager stores this.token; RootAppShell captures a token in its connection effect; a refresh storage/cookie write alone is not a proven WS token update |

### AUTH-02 client status/transport review — same freshly fetched source refs

The following describes the **refresh response**, rather than the original
protected-resource 401 that triggers renewal. It is read-only source inspection;
no mobile build, browser/device acceptance or deployed-version attestation was
performed. A server-side 503 never instructs token deletion, but cannot prevent
existing client code from doing so.

| Refresh outcome | iOS URLSessionAPIClient | Android TLTokenRefresher / authenticator | Web authRefresh / outer startup |
| --- | --- | --- | --- |
| 401 | Maps to unauthorized; refresh catch clears stored tokens and throws refreshFailed | Clears tokens; returns null, authenticator stops and exposes original protected-request 401 | Central helper clears only if stored refresh still matches failed snapshot; base/upload redirect only if credentials are gone; startup catch also clears |
| 403 | Refresh catch clears tokens and throws refreshFailed | Clears tokens; returns null; caller may see original protected 401 | Helper preserves tokens and propagates error; RootAppShell bootstrap catch still clears |
| 429 | Refresh catch clears tokens; no rate-limit-specific retry/preservation in that method | Preserves tokens, returns null; no Retry-After/backoff in refresher; original protected 401 may reach caller | Helper preserves tokens, propagates; no retry/backoff in helper; startup catch still clears |
| 500 / 502 / 503 / 504 | Each is an error caught by refresh catch; clears tokens | Each preserves tokens; returns null; authenticator can collapse transient refresh outcome into original 401 | Each preserves tokens in helper; base/upload propagate refresh error; startup catch still clears |
| Network timeout / lost connection | TransportFailed reaches refresh catch and clears; cancellation alone is rethrown without clearing | execute failure returns null, retains tokens; body read/decode failure also retains; original 401 can remain visible | Axios rejection without 400/401 retains tokens in helper; bootstrap rejection still clears. Plain refresh axios call sets no explicit timeout/retry loop |
| Lost response after successful rotation | Usually treated as transport failure and clears; cancellation may retain the now-consumed parent | Keeps old pair if no successful body/persist; subsequent old-refresh retry is 401 and clears | Helper keeps old pair if response never installed; bootstrap can clear immediately; subsequent old-refresh retry is 401 unless another tab already installed a new pair |
| Concurrent refresh | Normal/upload 401 paths call separate refresh operations; no shared flight or snapshot guard found; failure can erase another success, stale success can replace credentials | Per-instance synchronized lock reuses changed access after waiting; does not serialize multiple instances/processes; no compare-before-clear guard in rejected refresh branch | One flight shared by base/upload per tab; successful install and rejected-session deletion compare submitted snapshot; no cross-tab atomic refresh coordination |

Important outer-boundary findings:

- Web `RootAppShell.tsx:330–440` unwraps fetchAuthMe/profile initialization in
  one try/catch; its catch unconditionally removes access/refresh/user state and
  dispatches setLogout. `authSlice.ts:94–106` reduces fetchAuthMe failures to a
  message, losing status information. Thus claiming Web sessions survive all
  503s based only on authRefresh would be incorrect. This finding supplements
  the initial gate, which inspected the helper but did not identify this catch.
- Android `TLTokenAuthenticator.kt:64–68` returns null when renewal fails,
  regardless of whether refresh returned 401, 503 or a transport failure. The
  protected request can therefore still surface its original 401. The inspected
  bootstrap catches fresh-me failure and falls back to restored user state;
  other UI callers must not infer definitive token invalidity from that collapsed
  outcome. Token retention in the refresher is not proof of all UI behavior.
- iOS `URLSessionAPIClient.swift:732–780` turns all non-cancellation refresh
  failures into refreshFailed after clearing. It loses the distinction this
  server remediation introduces. A malformed 200 response also follows that
  catch; a failure saving the rotated pair occurs afterward and cannot recover
  the old consumed token.

Exact source:
[iOS refresh catch](https://github.com/hossein-sakkaki/TownLIT_iOS/blob/95179ad944a1731dee9c22036bbfead5d08159d7/TownLIT/Core/Networking/URLSessionAPIClient.swift#L765),
[Android refresher](https://github.com/hossein-sakkaki/TownLIT_Android/blob/cb59509327863128922eaf0cc99f2b8d1dc24176/core/network/src/main/kotlin/com/townlit/android/core/network/auth/TLTokenRefresher.kt#L129),
[Android authenticator](https://github.com/hossein-sakkaki/TownLIT_Android/blob/cb59509327863128922eaf0cc99f2b8d1dc24176/core/network/src/main/kotlin/com/townlit/android/core/network/auth/TLTokenAuthenticator.kt#L64),
[Web startup catch](https://github.com/hossein-sakkaki/TownLIT_F/blob/614756be5f075850a22c1b3af8729b86d2d3544c/src/app/RootAppShell.tsx#L431),
[Web status-losing thunk](https://github.com/hossein-sakkaki/TownLIT_F/blob/614756be5f075850a22c1b3af8729b86d2d3544c/src/redux/auth/authSlice.ts#L94).

Narrow client recommendations for separate client changes/releases:

1. iOS: retain tokens on 429, 5xx, timeout/network/decode failures; preserve a
   typed unavailable result instead of refreshFailed; clear only a definitive
   refresh credential denial for the still-current submitted snapshot. Share a
   refresh flight between normal/upload callers, and guard installs against
   logout/account switch. Do not treat a protected-resource 401 or arbitrary
   policy 403 as proof that every stored credential is invalid.
2. Web: preserve status/category through fetchAuthMe and the bootstrap boundary;
   on temporary failure retain credentials and show a retryable unavailable UI
   while server authorization remains denied. Keep existing snapshot guards.
   Review cross-tab coordination and update the WS connection's token after
   renewal in a separately tested client change.
3. Android: retain existing transient-error token retention; propagate a typed
   refresh-unavailable outcome through the authenticator/network/UI boundary,
   avoiding the ambiguous original 401. Review a shared refresher lifetime and
   compare-before-clear guards. Address CLIENT-01 independently before password
   V2. Do not change backend account policy to compensate.
4. First validate client fault/status/parallel-request/WS tests with synthetic
   staging endpoints, then release the iOS and Web fixes and identify actually
   deployed versions; validate Android's outer handling. Only after AUTH-01 and
   normal release approvals, canary the Backend status contract with flags/pins
   unchanged and observe nonsecret error rates/session retention. A server-only
   rollout cannot promise existing iOS/Web session preservation. A later modern
   dependency rollout remains separate. None of this order is deployed here.

Retries need bounded backoff/jitter and 429 Retry-After handling where present,
but no automatic retry scheme can recover a consumed parent whose new pair was
lost. Network stacks may retry at transport level; phase-specific transport
behavior was not executed on devices. Always keep ambiguous/lost-ack and
concurrent-refresh limitations visible; never promise idempotency from 503.

### CLIENT-01 — Android secure-password response incompatibility

At the inspected Android SHA, `AuthFlowDtos.kt:180` declares mandatory String
`refresh`/`access` and Boolean `is_member` in `ResetPasswordResponseDto`;
`DefaultAuthRepository.kt:681` requires `user` and constructs/stores an AuthSession.
`ChangePasswordResponseDto` exposes only message/error and changePassword returns
that message. There is no login_required handling in those current auth paths.
The secure server response intentionally omits JWT/user fields, so this is a
concrete source-contract incompatibility with enabling password-security V2,
not an integer-JWT-claim problem. Android was not changed in this task. Keep
that flag unchanged; updated clients/deployment acceptance are prerequisites.
This blocks a full-auth compatibility claim and future flag rollout. AUTH-01
and current refresh-client risks independently keep the present merge gate open.

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

Immutable source links:
[iOS refresh handling](https://github.com/hossein-sakkaki/TownLIT_iOS/blob/95179ad944a1731dee9c22036bbfead5d08159d7/TownLIT/Core/Networking/URLSessionAPIClient.swift),
[Android password DTOs](https://github.com/hossein-sakkaki/TownLIT_Android/blob/cb59509327863128922eaf0cc99f2b8d1dc24176/core/auth/src/main/kotlin/com/townlit/android/core/auth/model/AuthFlowDtos.kt#L180),
[Android password repository](https://github.com/hossein-sakkaki/TownLIT_Android/blob/cb59509327863128922eaf0cc99f2b8d1dc24176/core/auth/src/main/kotlin/com/townlit/android/core/auth/repository/DefaultAuthRepository.kt#L681),
[Web refresh handling](https://github.com/hossein-sakkaki/TownLIT_F/blob/614756be5f075850a22c1b3af8729b86d2d3544c/src/lib/authRefresh.ts).

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
