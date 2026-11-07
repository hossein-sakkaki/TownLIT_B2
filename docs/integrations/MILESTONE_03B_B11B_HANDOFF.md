# TownLIT B1.1B — dependency compatibility and trusted identity design

`docs/integrations/MILESTONE_03B_B11B_HANDOFF.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-06. Last Update by Hossein Sakkaki on 2026-11-06.

## Baseline and bounded outcome

**Audit/design checkpoint complete; no production-compatible common profile is
approved.** The maintained candidate installs and passes crypto/Gateway tests,
but fails two existing human refresh regressions. The minimal upgrade passes
those regressions but retains advisory-affected SimpleJWT. Do not adopt either
automatically or activate service authentication. Final measured evidence follows.

Direct GitHub PR metadata confirms PR #5 merged as
`00108e3eee45a67bdff8f80086875fb54af54211`, parents `429efd64` and `9aa42924`.
Freshly fetched `security/django-5.2-lts-20261022` matches that exact merge SHA.
New branch: `feat/milestone-03b-gateway-dependency-identity`. Previous B1.1A
checkout was clean; no work was reset, rebased or overwritten. No Backend
AGENTS.md exists. Existing B1/B1.1A acceptance/handoffs, repository setup/header
conventions, security/policy/registry/model boundaries and isolated CI were read.
Office main `5cb67e3cf87d838ceab672d4d0b270cb8cd9cf06`, its contract and
DR-03–06 are read-only references; no Office source changes.

This checkpoint audits disposable dependency profiles and specifies a future
composition boundary. It adds test/profile tooling and design only. No production
manifest, settings, human authentication, domain source, model/migration or public
security boundary changes are proposed. `UnavailableSecurity` remains active.

## Compatibility matrix

Version-specific PyPI metadata/advisory review: 2026-11-06, Python 3.12.14 local;
CI uses Python 3.12. Each matrix job is an independent disposable environment,
installs a generated **full Backend manifest**, runs pip check, existing human
regressions and fixed-socket disposable MySQL. Never overlay conflicting pins.

| Dependency | Baseline control | Minimal common experiment | Supported common candidate |
| --- | --- | --- | --- |
| Django | 5.2.18 | 5.2.18 | 5.2.18 |
| PyJWT | 2.8.0 | 2.15.1 | 2.15.1 |
| cryptography | 43.0.1 | 50.0.2 | 50.0.2 |
| pyOpenSSL | 24.2.1 | 26.4.0 | 26.4.0 |
| cffi | 1.17.1 | 2.1.1 | 2.1.1 |
| SimpleJWT | 5.3.1 | 5.3.1 | 5.5.1 |
| joserfc | absent | 1.8.0 | 1.8.0 |
| django-cryptography-5 | 2.0.3 | 2.0.3 | 2.0.3 |
| All other direct pins | unchanged | unchanged | unchanged |

The common profile requires Python >=3.11 because of joserfc; Python 3.12 is
the tested target. Actual deployed Python/platform/OpenSSL builds remain an
inventory/release prerequisite. This is not a Django major-version upgrade.
The durable [dependency metadata snapshot](B11B_DEPENDENCY_REVIEW.json) records
15 exact package/version constraints and advisory lists, including untested
HTTP-signature candidate metadata, without installing it.

### Observed upstream human-token differences (upgrade blockers)

An isolated no-database probe using a synthetic integer-id user and the upstream
`RefreshToken.for_user` returned integer `user_id=7` under SimpleJWT 5.3.1 but
string `user_id="7"` under 5.5.1. This can affect clients even if Backend ORM
lookups and existing regressions accept both. The probe used public synthetic
Django settings, no application or production user. Direct source comparison
also shows 5.5.1's refresh serializer checks the current user/authentication rule
and records rotated outstanding tokens; 5.3.1 lacks those additions. Actual
client contracts, disabled/deleted-account refresh responses and blacklist
retention/rotation need upgrade-specific acceptance; no source was changed to
hide these differences.

The PyPI feed marks the inactive-user advisory fixed in 5.5.1, but the inspected
low-level `for_user` still mints for an inactive synthetic user and logs a warning.
It is **not an authentication check** in either version. Candidate
CHECK_USER_IS_ACTIVE defaults true; future configuration review must preserve
active-user checks at authentication/refresh boundaries. Do not infer security
from a version number or assume the advisory removes all issuance responsibilities.

Source inspection identifies a concrete interaction: the existing custom refresh
serializer sends the signed raw user_id claim into `session_generation_matches`,
which rejects non-int IDs when AUTH_SESSION_GENERATION_ENFORCE is enabled.
SimpleJWT 5.5.1's string IDs reject otherwise current refresh tokens; the
completed full regression run confirmed both affected tests below. Therefore do not disable enforcement or loosen validation to make the matrix pass.

Therefore a compatible resolver and green selected tests would identify the
safest *candidate*, not prove a behavior-identical or automatically deployable
human authentication upgrade. A separate reviewed upgrade/client decision is
still necessary. Production pins and behavior remain unchanged in this PR.

The minimal profile isolates the crypto/PyJWT transition but retains vulnerable
SimpleJWT; it is a diagnostic control, **not a recommended deployment profile**.
The supported candidate upgrades SimpleJWT too. Both retain Django 5.2 LTS and
all existing human auth source/settings. Exact generated profiles come from
`scripts/ai_gateway_dependency_profile.py`; it rejects unexpected baseline pin
drift and unknown profiles. It never writes requirements.txt. CI uses the same
emitter; baseline output is byte-identical to requirements.txt.

### Constraints and security review

- pyOpenSSL 24.2.1 requires cryptography >=41.0.5,<44. Modern joserfc 1.8.0
  requires >=45.0.1, so the baseline cannot host the B1.1A stack unchanged.
- cryptography 50.0.2 requires cffi >=2.0.0; cffi 1.17.1 also blocks resolution.
  pyOpenSSL 26.4.0 accepts cryptography >=49,<51. The candidate satisfies both.
- SimpleJWT 5.5.1 advertises Django 5.2 and Python 3.12 support and permits
  current PyJWT. 5.3.1 has GHSA-5vcc-86wm-547q (disabled-account validation,
  fixed 5.5.1). Source/session safeguards do not constitute advisory clearance.
- Baseline pyOpenSSL has GHSA-vp96-hxj8-p424 and GHSA-5pwr-322w-8jr4 (callback
  fail-open and cookie buffer handling, fixed 26.0.0). Baseline PyJWT and crypto
  advisories are detailed in B1.1A's handoff and remain unremediated in production.
- Version-specific feeds for the selected current PyJWT/cryptography/pyOpenSSL/
  SimpleJWT/joserfc/cffi and retained Django/encrypted-field versions reported no
  known advisories at review. That is not a complete Backend audit or a future
  guarantee. No changes to production pins are authorized by this finding.
- django-cryptography-5 2.0.3 requires Django >=2.2 and cryptography >=3.4.4 but
  owns a modified Fernet/AES-CBC/signing/KDF format. A permissive version range
  does not prove historical ciphertext or runtime compatibility. Existing direct
  Fernet users include account device/reset flows and pastoral_crypto; API/APNs
  and TLS consumers need their own release regression before a real upgrade.

Sources: version-specific `https://pypi.org/pypi/<package>/<version>/json` for
all table entries; upstream pyca/cryptography, pyca/pyopenssl, jpadilla/pyjwt,
jazzband/djangorestframework-simplejwt, authlib/joserfc. Consult B1.1A for the
prior exact advisory IDs. No OAuth/HTTP-signature extra or second JWT stack was
added to production.

## Actual evidence at first checkpoint

Local baseline-core disposable venv install/pip check passed; **4/4** focused
checks passed: PyJWT/HMAC positive and wrong-key/algorithm rejection, encrypted
field round trips, Fernet compatibility/wrong-key rejection and ephemeral
pyOpenSSL/cryptography X.509 object conversion. The certificate test is not mTLS.

Supported-core disposable venv install/pip check passed; **15/15** passed (the
four compatibility tests plus 11 existing B1.1A ES256/security-boundary tests).
Committed ciphertext contains public artificial text generated under baseline
cryptography 43.0.1 and django-cryptography-5 2.0.3 with explicit public test-only
keys/settings. It is not production data or a private key. Candidate reads of
that fixture prove a narrow old-to-new format check; no production-history or
new-to-old rollback assurance follows. These initial local results were recorded before CI; completed Backend/DB
results are in the final matrix below; focused local venvs do not contain the full production manifest.

Minimal-core disposable venv install/pip check also passed; **15/15** tests
passed. Two separate resolver-negative probes returned ResolutionImpossible:
cryptography 50.0.2 + pyOpenSSL 24.2.1 (crypto <44), and cryptography 50.0.2 +
cffi 1.17.1 (cffi >=2 required). A naive baseline-manifest overlay with modern
cryptography was rejected too. These are expected incompatibility results,
not failing runtime tests. Full candidate resolution remains subject to CI.

Profile emitter allowlisted-change checks, scoped Ruff and 32 headers passed.
The existing CI matrix preserves all 66 selected Backend regressions for human
issuance/refresh/revocation/password/reset/2FA/redaction and Gateway denial/domain
isolation, plus 28 Gateway tests on MySQL and SQLite. Candidate jobs explicitly
run ES256 in the **same** full-manifest environment. Final results are below.

## Trusted identity composition proposal

No runtime composer or usable service identity is implemented here. See
[MILESTONE_03B_B11B_TRUSTED_IDENTITY_DESIGN.md](MILESTONE_03B_B11B_TRUSTED_IDENTITY_DESIGN.md)
for the proposed trust inputs, equality/version bindings, rejection order and
future mTLS/RFC 9421 prerequisites. B1.1A claims alone still fail existing policy.

## Recovery and next safe step

Fetch the existing feature branch/PR, inspect local work and remote SHA before
resuming. Do not reset or change the approved base. To emit a disposable manifest:

```
python scripts/ai_gateway_dependency_profile.py supported > ../b11b-supported.txt
python -m venv ../b11b-supported-venv
../b11b-supported-venv/bin/python -m pip install -r ../b11b-supported.txt
../b11b-supported-venv/bin/python -m pip check
../b11b-supported-venv/bin/python -m apps.ai_gateway.tests.run core test apps.ai_gateway.tests.dependency_compatibility apps.ai_gateway.tests.service_tokens --noinput -v 2
```

The full matrix workflow runs existing real disposable MySQL migrations and
human regression commands. Its generated environment is a test proposal only;
do not copy candidate pins into production automatically. Retain receipts,
working files and CI evidence across interruptions. Keep the new PR Draft;
no merge, deploy, live identity, credential, Office connection or capability.

Next safe implementation: after reviewing matrix results, propose a separately
reviewed dependency-upgrade PR with ciphertext/real-client rollback evidence,
then an internal typed composition seam with fake trusted adapters and negative
vectors. Keep HTTP unavailable. DR-03/04/05/06/08 and production release decisions
remain open; passing tests do not approve CA, proxy topology, issuers or grants.


## First pushed checkpoint

First pushed implementation/test/design checkpoint:
`473a3b9694be7effa529228128282a4344e3a4c9`;
Draft PR https://github.com/hossein-sakkaki/TownLIT_B2/pull/6.
[Matrix run 42347481184](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42347481184)
is associated with that exact head. All three full Backend manifests installed
and passed pip check; compatibility smoke tests passed, and both modern common
profiles passed the explicit ES256 suite in those same environments. The final
MySQL/human-regression table below supersedes that intermediate observation.
No human compatibility conclusion was inferred from installation success.


### Required follow-up for supported-profile incompatibility

Do not select the vulnerable minimal profile as a production workaround. Preserve
all unchanged auth regressions; the supported failure is a measured compatibility
blocker. A separate narrowly scoped upgrade proposal may pair the six direct
pin replacements plus joserfc with a reviewed canonical user-ID boundary:
validate a verified token's canonical positive decimal string (or legacy integer)
against the actual user PK type before session-generation checks. Reject bools,
floats, signs, whitespace, leading-zero aliases, excessive length and overflow;
never normalize an unsigned caller value or treat service sub as a Django user.
This is a future proposal, not an auth code change in this checkpoint.

That proposal also needs explicit disabled/deleted-user refresh/error-contract,
rotated blacklist behavior, legacy/current claim-type, revocation/store-outage,
real client/SSO/WebSocket and ciphertext rollback acceptance. No dependency
upgrade may silently turn off active-user/session checks or hide expected test
failures. Only after resolving these blockers can a common stack be proposed for
production; trusted service identity composition remains a separate internal,
disabled checkpoint as described in the design.


## Final measured compatibility matrix

[Run 42347481184](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42347481184)
completed with overall **FAILURE**, specifically the supported profile's human
refresh tests. Direct check-runs API and completed job logs bind every result to
feature SHA `473a3b9694be7effa529228128282a4344e3a4c9`, tested with proposed
merge ref `88a6b88356b7d981de5a632c05b73a5fa5ebe9e4` against the verified base.
The proposed merge is only a CI ref; this PR remains Draft and unmerged.

| Actual check | Baseline | Minimal common experiment | Supported common candidate |
| --- | --- | --- | --- |
| Complete generated Backend manifest + pip check | PASS | PASS | PASS |
| Four crypto/interoperability/baseline-ciphertext tests | 4/4 PASS | 4/4 PASS | 4/4 PASS |
| B1.1A ES256 in that same full-manifest environment | N/A: joserfc absent | 11/11 PASS | 11/11 PASS |
| Gateway MySQL | 28/28 PASS | 28/28 PASS | 28/28 PASS |
| Gateway SQLite | 24 PASS / 4 MySQL-only skips | 24 PASS / 4 MySQL-only skips | 24 PASS / 4 MySQL-only skips |
| Gateway drift, reversible migration and Backend check | PASS with baseline warnings | PASS with baseline warnings | PASS with baseline warnings |
| Selected Backend human/security/domain-boundary tests | 66/66 PASS | 66/66 PASS | **64 PASS / 2 FAIL**, no skips |
| Disposable MySQL cleanup | PASS | PASS | PASS |
| Overall matrix job | SUCCESS | SUCCESS, diagnostic only | **FAILURE: incompatible** |

Exact jobs: [baseline 128328252770](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42347481184/job/128328252770),
[minimal 128328252758](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42347481184/job/128328252758),
[supported 128328252753](https://github.com/hossein-sakkaki/TownLIT_B2/actions/runs/42347481184/job/128328252753).
Python 3.12.16 / disposable MySQL 8.4.13. Each profile applied the complete real
Backend test migration graph, including accounts/0105 and its own third-party
migrations, with no fake migrations or production database access.

The independent B1.1A isolated profile job also passed 11/11, and GitGuardian
passed (one commit scanned, no secrets detected). These do not override the
supported-profile failure or approve the whole Backend dependency stack.

### Exact supported-profile failures and disposition

Both unchanged tests in `apps.accounts.tests.test_session_generation_enforcement`
failed with **401 != 200**:

- `test_current_refresh_still_rotates` (source line 85).
- `test_legacy_zero_refresh_accepted_before_first_revocation` (source line 100).

This matches the independently observed integer-to-string user_id transition
and the existing strict integer session-generation boundary. The minimal profile
is an effective control: it differs from supported only in SimpleJWT and passes
all 66. Neither source nor test expectations were changed. No enforcement flag
was disabled. This is a fail-closed compatibility/availability break, not proof
of a JWT authorization bypass. The supported candidate is **not safe to adopt
under the current unchanged human-auth behavior**.

The remaining 64 supported tests passed, including issuance/access validation,
revocation/reset and boundary checks outside those two refresh paths. Do not
claim refresh compatibility or full Backend-suite clearance from those passes.
No fully acceptable supported common production profile was established.

### Actual skips and warnings

Each SQLite profile intentionally skips the same four MySQL concurrency cases:
conflicting payloads, nonce winner, revocation/receipt serialization and same-key
serialization. All four run successfully on MySQL in every profile. Baseline
intentionally skips the in-environment ES256 step because it lacks joserfc; the
separate B1.1A job remains successful. The supported job skips setup-python's
post-success cache step after the failed regression command, while its always-run
database cleanup succeeds. No human regression test is skipped or waived.

Observed existing warnings: CKEditor 4.22.1 unsupported/unfixed-security notice;
Requests/urllib3 2.0.4 and chardet 7.7.0/charset_normalizer 3.2.0 compatibility;
eight MySQL models.W036 conditional-unique warnings across accounts, boundaries,
main, profiles and sanctuary (nine system issues including CKEditor); and
Actions Node punycode/url.parse deprecations. Such conditional constraints remain
unenforced on MySQL. Expected fault-injection logs accompany passing rollback/
redaction cases. No warning was suppressed, remediated or release-approved here.

### Review readiness and final recovery

B1.1B is ready for owner review **as a compatibility audit and trusted-identity
design checkpoint**, with an explicit unresolved adoption blocker. The common
crypto target is technically compatible in the diagnostic profile; adopting
maintained SimpleJWT requires the separately reviewed human-ID/refresh/client
work above. Do not approve the vulnerable diagnostic stack instead. Production
pins, human source/settings, Gateway routes/security/verifier/model/migration
source and Accounting/Advancement are byte-unchanged from the verified base.
Office source remains untouched; no runtime composer or live service identity
was added. DR-03/04/05/06/08 and release decisions remain open.

The final evidence correction is documentation/JSON only; no runtime, workflow,
manifest emitter, fixture or test code differs from tested implementation
`473a3b9694be7effa529228128282a4344e3a4c9`. Final SHA is recorded in PR #6 and
the completion report, since a file cannot contain its own commit SHA. Fetch
that same branch, verify local/remote/PR heads, preserve local work, and use the
profile emitter/disposable commands above to reproduce results. Expect the
supported job to remain red until a separately authorized fix is implemented;
do not alter the regression expectations to hide it. A documentation push may
schedule a fresh matrix run; the completed run above is tied to its exact tested
implementation SHA, not a newer head.
