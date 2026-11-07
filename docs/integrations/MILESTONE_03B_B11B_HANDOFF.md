# TownLIT B1.1B — dependency compatibility and trusted identity design

`docs/integrations/MILESTONE_03B_B11B_HANDOFF.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-06. Last Update by Hossein Sakkaki on 2026-11-06.

## Baseline and bounded outcome

Direct GitHub PR metadata confirms PR #5 merged as
`00108e3eee45a67bdff8f80086875fb54af54211`, parents `429efd64` and `9aa42924`.
Freshly fetched `security/django-5.2-lts-20261022` matches that exact merge SHA.
New branch: `feat/milestone-03b-gateway-dependency-identity`. Previous B1.1A
checkout was clean; no work was reset, rebased or overwritten. No Backend
AGENTS.md exists. Existing B1/B1.1A acceptance/handoffs, repository setup/header
conventions, security/policy/registry/model boundaries and isolated CI were read.
Office main/contract/DR-03–06 are read-only references; no Office source changes.

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
new-to-old rollback assurance follows. Full Backend/DB results are pending until
CI completes; focused local venvs do not contain the full production manifest.

Profile emitter allowlisted-change checks, scoped Ruff and 32 headers passed.
The existing CI matrix preserves all 66 selected Backend regressions for human
issuance/refresh/revocation/password/reset/2FA/redaction and Gateway denial/domain
isolation, plus 28 Gateway tests on MySQL and SQLite. Candidate jobs explicitly
run ES256 in the **same** full-manifest environment. Results will be appended.

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
