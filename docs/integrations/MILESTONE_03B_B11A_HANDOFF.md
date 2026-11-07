# TownLIT B1.1A — isolated synthetic service-token verification

`docs/integrations/MILESTONE_03B_B11A_HANDOFF.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-06. Last Update by Hossein Sakkaki on 2026-11-06.

## Verified source and scope

Backend base/target `security/django-5.2-lts-20261022` freshly verified at
`429efd647bbceb30f71389f09b7bae6dfd33212a`; main is
`544b96b0b42434d9f52d672a6a418c21d9967eb6`. Feature
`feat/milestone-03b-gateway-jwt-verification` was absent remotely and created
from that exact base in a new clean checkout. Existing `/workspace/TownLIT_B`
(main `6410d1d6c5efbf420ceeb0c0f37f846c4c71207d`) and Office (work
`867f9af764cbc2cb4f074865df3b3a3a9616aa3c`) were clean and preserved.
No Backend AGENTS.md exists in this baseline; read existing source conventions,
B1 acceptance/handoff, Gateway security/registry/policy/models/migration/tests/CI.

Read-only Office main freshly fetched at
`5cb67e3cf87d838ceab672d4d0b270cb8cd9cf06`: AGENTS.md, Gateway contract,
03B plan/decision register and final O1 handoff. Office local organization PKs
and Backend metadata UUIDs remain different provisional references; this work
establishes no authoritative mapping. No Office source was changed.

Only `service_tokens.py` supplies a directly invoked synthetic verifier.
`UnavailableSecurity`, routes, settings, human JWT dependencies, domain source,
metadata schema and grants are unchanged. No setting connects this component to
HTTP. A signature-checked `ServiceTokenClaims` is **not VerifiedIdentity** and is
rejected by existing policy. No domain authority follows from any claim.

## Dependency review and separate test environment

Review date 2026-11-06 (America/Vancouver). Host Python 3.12.14 initially had
cryptography 50.0.0, PyJWT 2.13.0 and no Django. These host packages were not
assumed approved. Backend manifest remains Django 5.2.18, cryptography 43.0.1,
PyJWT 2.8.0, SimpleJWT 5.3.1 and pyOpenSSL 24.2.1.

Inspected version-specific PyPI metadata and its OSV-linked advisory records:

- [PyJWT 2.8.0](https://pypi.org/pypi/PyJWT/2.8.0/json): reported advisories
  include unsupported critical headers (GHSA-752w-5fwx-jx9f), mixed HMAC/JWK
  confusion (GHSA-xgmm-8j9v-c9wx), JWKS destination/rate/redirect issues,
  malformed encoding and resource limits. Do not use it for this verifier.
- [cryptography 43.0.1](https://pypi.org/pypi/cryptography/43.0.1/json): reported
  advisories include bundled OpenSSL (GHSA-79v4-65xg-pq4g,
  GHSA-537c-gmf6-5ccf), EC subgroup validation (GHSA-r6ph-v2qm-q3c2), and X.509
  name constraints/chain exhaustion. It is not approved here.
- Maintained [joserfc 1.8.0](https://pypi.org/pypi/joserfc/1.8.0/json) requires
  Python >=3.11 and cryptography >=45.0.1. Authlib 1.9.5 requires Python >=3.10,
  joserfc >=1.6.8 and cryptography >=45.0.1; its broader OAuth surface is unneeded.
  PyJWT 2.15.1 (Python >=3.9) is maintained but shares the human stack's import
  namespace. jwcrypto 1.5.8 supports cryptography >=39 but still requires a
  reviewed crypto backend. These are alternatives, not extra dependencies.
- Selected exact **joserfc 1.8.0 + cryptography 50.0.2**, both reporting empty
  vulnerability lists in their version-specific PyPI metadata at review time.
  Upstream: https://github.com/authlib/joserfc and https://github.com/pyca/cryptography.
  This is a bounded advisory review, not a complete audit or future guarantee.

The new `requirements.ai-gateway-b11a.txt` is for a **separate venv only**, never
an overlay on requirements.txt. Modern crypto conflicts with baseline pyOpenSSL's
crypto upper bound. Do not upgrade the baseline silently. The constructor requires
these exact reviewed JOSE/crypto versions and supports only `synthetic-*`
environments. Baseline deployment does not import this module. Integrating a
maintained crypto stack with the full Backend remains a separate prerequisite.

## Exact test-only profile and negative matrix

| Control | Implemented profile / negative cases |
| --- | --- |
| Signature/key | joserfc JWT decode with ES256-only allowlist, locally supplied cryptography P-256 public-key objects; no private/symmetric/wrong-curve key registration. Unknown kid, forged signature, tampered payload and HMAC/public-key confusion deny. |
| Header | Exactly alg=ES256, typ=at+jwt, bounded kid; all other headers deny, including jku/x5u/jwk/x5c/crit/b64/cty. No URL lookup or key destination exists. |
| Trust/environment | Exact issuer `https://issuer.<synthetic-environment>.example.invalid/office`, exact scalar audience `townlit-ai-gateway:<synthetic-environment>`, exact environment claim. Audience arrays, prefixes, wrong environments and actual staging/production configuration deny. Each verifier has its own local registry; cross-environment tokens deny even if a test deliberately reuses a public key. |
| Required schema | Exactly iss/aud/sub/exp/iat/nbf/jti/agent_id/organization_id/scopes/environment. Unknown claims deny. sub and jti are nonempty ASCII labels <=128 chars. Only phoebe/silas/micah; Chloe and unregistered agents deny. |
| Time | Exact nonnegative integer NumericDates <=2^53-1; iat <= nbf < exp <= iat+300. Library validates time with configured 0–30s skew. Bool/string/float/missing dates, future iat/nbf beyond skew, expiry and >300s lifetime deny. exp at now-skew denies. |
| Organization/scope | Canonical lowercase UUID string; 1–16 unique nonempty ASCII scope labels <=128 chars. No wildcard interpretation or lookup. These are untrusted permission assertions, not records/grants. |
| Ambiguity/resources | <=8192-char compact token, <=512-byte header, <=4096-byte payload, exactly 64 signature bytes; strict unpadded canonical base64url, UTF-8 JSON objects, no duplicate or escaped duplicate keys, nonfinite JSON constants or trailing JSON. JSON recursion/errors become fixed redacted rejection. Structural parsing supplements JOSE; no signature math is handwritten. |
| Isolation | In-memory ephemeral signing keys generated inside tests only; no committed key/credential, issuer connection, domain dispatch or production secret. Existing runner clears inherited environment and blocks Python network/subprocess I/O. |

The synthetic claim schema deliberately omits contract policy_version and cnf:
unknown fields are rejected, so this is not a complete contract access token.
Future certificate/thumbprint and policy binding must define a new reviewed
profile. Access-token jti is reusable during validity, not single-use request
replay protection. No replay/revocation database or current principal check is
performed. No mTLS or RFC 9421 assurance follows from these JWT tests.

## Actual validation

Initial coherent checkpoint: Python 3.12.14; isolated dependency install and
pip check passed. Explicit suite: **11/11 passed**, no skips, no database setup.
31 Gateway/header-checker scope source headers, scoped Ruff lint/format and
`git diff --check` passed. The first two focused attempts had one test-fixture
error each because joserfc correctly refused importing public DER as an HMAC
key. The final attack fixture constructs the library's symmetric-key object
explicitly, then uses JOSE signing; the verifier rejects that actual HMAC token.
No signature math is handwritten. Existing baseline regressions/hosted CI are
pending at this first checkpoint; subsequent evidence will be appended.

CI adds a separate venv/job for this suite. The existing full-manifest baseline
job retains all MySQL/SQLite, migration and human security tests. Its stale
pre-B1 merge SHA check is advanced to the user-authorized current base
429efd647bbceb30f71389f09b7bae6dfd33212a; no base ref/history is changed.
The explicit suite is `apps.ai_gateway.tests.service_tokens` (no test_ prefix)
so baseline discovery does not import the separate modern crypto stack.

## Deferred controls and recovery

DR-03 is only partially evidenced for this synthetic JWT profile; it and DR-06
remain open for production approval. Deferred: Backend dependency reconciliation,
trusted principal/key lifecycle and revocation, current grants, authoritative
org/record bindings, certificate/mTLS/proxy verification, request signatures,
issuance/private_key_jwt, replay/rate stores, all capabilities/tools/domain data,
key rotation/custody, staging and production. No merge/deployment is authorized.

Next safe B1.1 checkpoint: review dependency reconciliation and define synthetic
trusted-principal/certificate/current-grant composition without wiring HTTP.
Keep `UnavailableSecurity` active; complete mTLS/request-proof decisions and
negative evidence separately before considering a usable identity.

Recovery: fetch this feature branch, inspect working tree and remote SHA, compare
against the exact approved base, and resume the existing Draft PR. Do not reset
local work, merge/rebase the baseline, mint credentials or enable a service.
Create a fresh venv, install only requirements.ai-gateway-b11a.txt, then run:

```
python -m apps.ai_gateway.tests.run core test apps.ai_gateway.tests.service_tokens --noinput -v 2
```

Use a different venv with unchanged requirements.txt for baseline Gateway/full
Backend regressions. CI must run both profiles; passing only the isolated JOSE
suite does not establish compatibility with the Backend runtime. Exact final
pushed SHA and Draft PR URL belong in the PR and completion report (a document
cannot include its own containing commit SHA).
