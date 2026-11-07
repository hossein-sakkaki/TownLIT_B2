# TownLIT B1.1B — trusted service identity composition proposal

`docs/integrations/MILESTONE_03B_B11B_TRUSTED_IDENTITY_DESIGN.md` · TownLIT-Backend
Created by Hossein Sakkaki on 2026-11-06. Last Update by Hossein Sakkaki on 2026-11-06.

## Status and invariants

Design only, not an HTTP authentication implementation. The current
`SyntheticServiceTokenVerifier` returns `ServiceTokenClaims`; it is deliberately
incompatible with `VerifiedIdentity`, and current HTTP invokes only
`UnavailableSecurity`. No dependency profile, setting, DTO, grant or synthetic
certificate context may bridge that boundary in B1.1B.

A future composer needs four independent inputs: signature-checked token claims,
a currently registered service principal, current authoritative scope/grants,
and independently verified certificate context. JWT signature proves issuer
assertions; it does not prove certificate possession, principal enrollment,
current grants, Office-org mapping, request integrity or domain ownership.

## Proposed types and trust provenance

| Input/output | Producer and proposed contents | What must never qualify |
| --- | --- | --- |
| VerifiedTokenAssertions | Reviewed JOSE verifier; issuer/audience/environment, signing kid, sub, agent, organization ref, scopes, iat/nbf/exp/jti, policy_version and cnf.x5t#S256 | Raw decoded dict or existing human JWT; B1.1A's synthetic type as a complete production profile |
| RegisteredPrincipalSnapshot | Trusted registry lookup by exact (environment, issuer, sub); principal UUID, agent, active/revoked status, current policy revision, approved issuer signing keys and enrolled certificate/request-key associations | Agent-name lookup alone, Django user/staff/superuser, an HTTP-selected registry/class or token-provided key URL |
| VerifiedCertificateContext | Trusted direct TLS adapter, or authenticated/allowlisted terminator adapter; exact verified leaf DER fingerprint, trust policy/terminator identity, verified chain/EKU/validity, current certificate status and request/connection binding | cnf claim, client certificate text, X-SSL/X-Client-Cert/X-Agent-ID headers, a boolean SUCCESS or a fake context constructor alone |
| AuthoritativeGrantSnapshot | Trusted current principal/organization/operation/record/grant lookup with policy revision and revocation status; module-specific record selectors later | Claimed scopes, fake Office grants, metadata UUID/name/creator inference or local Office approval |
| BoundServiceSubject | Internal immutable value with principal UUID/agent/environment, canonical Backend org FK/public_id, registered Office organization reference, certificate fingerprint, policy revision, token issuer/jti/expiry and granted-scope intersection | Django User or session; no domain operation can consume this directly |
| AuthorizedRequestContext | Future request-proof/replay/current-operation authorization boundary over BoundServiceSubject and exact request | A token, cached identity, certificate result or broadly scoped subject alone |

Interfaces are a proposal, not registered implementations. Python type checks
cannot make a forged object cryptographically trusted: only fixed trusted
adapter call paths may construct proof/snapshot values. No dynamic setting,
caller-specified provider, model-supplied destination or general-purpose factory.
Store no raw token, private key, full certificate, arbitrary DN or sensitive
claims in logs/audit; use bounded server IDs and approved internal references.

## Exact binding rules and rejection order

1. Enforce the future fixed environment/security profile and request limits.
   Missing configuration, registry/store failure, malformed input or unknown
   operation denies. Chloe and unregistered agents deny even with a bad grant.
2. Verify the access token using fixed ES256, exact issuer/audience/environment,
   typ=at+jwt and approved local issuer key registry. Retain B1.1A's duplicate,
   claim/type/time/size/header rejection rules; do not fetch token key URLs.
   Issuer signing keys, principal request keys and client certificate keys have
   different roles; one approved token kid cannot enroll the others.
3. Resolve principal by exact environment+issuer+sub and recheck active/revoked
   state. agent_id must equal that registration and an allowed operation agent.
   A syntactically valid subject is not an enrolled principal. Enforce current
   signing-key status and issuer/jti/principal revocation before using a token.
4. Obtain independently verified certificate context from the trusted TLS path.
   Validate trust anchor/chain, intended client-auth usage, validity, permitted
   algorithms, revocation policy and enrolled principal/environment association.
   Do not infer a principal from certificate CN, organization text or header.
5. Require exactly `cnf: {"x5t#S256": "<canonical-base64url-SHA256-leaf-DER>"}`.
   Decode a canonical unpadded 43-character base64url string to exactly 32 bytes;
   compare using reputable constant-time primitives against BOTH verified peer
   leaf fingerprint and current enrolled principal certificate fingerprint.
   Compute fingerprints with library SHA-256 over leaf DER, not PEM text, chain,
   issuer certificate or textual hex. Wrong certificate, unregistered overlap,
   revoked/expired certificate or untrusted context denies. JWT's 30-second skew
   is not permission to extend certificate validity. A self-signed test object
   is not a verified peer.
6. Require a bounded opaque `policy_version` string equal to the registry's
   current immutable revision for that principal/environment/organization.
   Principal, binding and current-grant snapshots must share the same revision
   or deny/retry internally under a consistent transaction. Never trust a
   caller's version, compare lexicographically, silently downgrade, or use a
   default revision. A grant/revocation/binding change increments revision and
   invalidates cached authorization; no cache is allowed until consistency and
   invalidation evidence exists. No current model supplies this mechanism yet.
7. Require token organization_id to equal the authoritative Backend
   `Organization.public_id` resolved through a current, approved environment-
   scoped binding. Resolve the Office organization's stable public reference
   from the trusted principal/binding registration, never caller actor/task text.
   Office's local integer organization PK is not that reference. Current
   `OfficeOrganizationBinding` UUIDs are provisional and have no authoritative
   Organization FK: they cannot satisfy this rule. Future schema must use an
   explicit Backend org FK, an exact Office namespace/reference and reviewed
   lifecycle/revocation/uniqueness constraints; no blanket legacy backfill.
8. Intersect token scopes with current principal+agent+environment+organization+
   exact operation/version/record grants and the static operation allowlist.
   Empty, revoked, expired, mismatched or ambiguous bindings deny. Do not treat
   intersection as domain authorization: required related-record/FK selectors
   and classification checks still apply before any operation. No wildcard,
   ContentType/ORM selector or superuser bypass. Current only capability is
   unavailable metadata; no domain operation is added.
9. Return at most BoundServiceSubject internally, with bounded expiry and the
   policy/certificate/token references needed for revalidation. Never cast the
   assertions into today's metadata `VerifiedIdentity`. A future
   AuthorizedRequestContext also requires RFC 9421 proof and replay checks over
   the actual request, plus current grants at execution/replay time.

Principal -> organization binding -> grant -> receipt -> audit remains the B1
metadata lock order. Any future composer/operation must revalidate under a
consistent authorization snapshot and share revoke serialization; a previously
composed subject never freezes permission through expiry. Select exact labels
again after lookup because MySQL collation may be case-insensitive. Authoritative
domain rows and downstream locks require a separately reviewed order.

## Token schema evolution

B1.1A accepts an exact synthetic schema and **rejects policy_version/cnf**.
Do not weaken its unknown-field check or repurpose its tests as production proof.
Propose a separate explicitly versioned profile with required policy_version and
cnf only after the trusted adapter/registry contracts are reviewed. Missing,
unknown, duplicate/nested-duplicate or malformed confirmation fields must deny;
there is no compatibility fallback to bearer-only authentication. Any Office
client agreement/contract update is future read-only coordination here.

## Prerequisites before mTLS implementation or enablement

- Review the common dependency candidate against the full Backend, original
  encrypted-field formats, real-client/session/SSO expectations, supported
  deployment Python/OpenSSL builds and rollback policy; update production pins
  only in an explicitly reviewed upgrade. No new settings in this checkpoint.
- Decide environment-specific CA/trust anchors, issuer/audience, principal/key/
  certificate enrollment and revocation owners, key custody, certificate EKU/SAN
  profile, TLS versions/algorithms, rotation overlap and emergency deny behavior.
- Choose direct TLS or the exact TLS terminator and authenticate its hop to the
  app. Block direct app bypass, strip/overwrite all caller certificate headers,
  use an authenticated metadata channel, define chain-validation/revocation
  failure behavior and bind context to the actual request/connection. A trusted
  source-IP/header alone is insufficient. Unknown hops/headers fail closed.
- Test actual ephemeral-CA TLS handshakes and negative chains, wrong EKU/SAN,
  expiry, revocation/unavailable status, environment crossing, header spoofing,
  terminator bypass and rotation; DTOs/self-signed X.509 conversion cannot count.
- Add independently reviewed authoritative registry/policy-version/org schema
  and current-grant consistency, bounded redacted audit and shared store failure
  tests. Staging topology/configuration needs explicit authorization first.

## Prerequisites before RFC 9421 implementation or enablement

Choose and advisory-review a maintained compatible HTTP Message Signatures
library; no library is approved by B1.1B. Ratify one signature profile including
algorithm, principal-specific registered request key, canonicalization, covered
components, signature label, created/expires bounds and key/certificate roles.
Cover method, authority, target URI including query, Content-Digest over actual
body bytes, Authorization, content-type, timestamp/nonce, organization/purpose/
correlation context, If-Match and Idempotency-Key when present. Define empty-body
and bounded/streamed quarantine upload handling. Reject duplicate/ambiguous
headers, URI/path/query normalization differences, unsupported critical features,
redirects, unsigned context and algorithm/key confusion.

Require trusted-proxy byte preservation and independently test captured original
request bytes through the chosen ingress; application-reconstructed URLs are not
authoritative signed targets by default. Decide canonical vectors jointly with
Office's future transport; O1's offline domain hash is not RFC 9421 proof or B1
metadata canonicalization. Access-token jti remains reusable, not a request nonce.
Use atomic shared request replay reservations, bounded timestamps and fresh
nonces on retries; stores/rate/audit outages must deny. Preserve original business
idempotency keys/hash and current authorization on cached receipt replay.

## Future synthetic acceptance matrix and narrow implementation proposal

| Vector | Required result/evidence |
| --- | --- |
| Good signed claims only | Reject as usable identity; existing B1.1A test already proves this. |
| Valid token + inactive/unknown/wrong-agent principal | Deny before authorization, no user lookup or domain SQL. |
| Token/registry/verified-cert thumbprint mismatch, absent cnf or forged headers | Deny; an equal caller-provided fingerprint does not prove TLS possession. |
| Old policy version, changed/revoked/expired grant or registry outage | Deny even while token is cryptographically valid; serialize revoke races on disposable MySQL. |
| Wrong/unbound Office or Backend organization, same record number in another org | Deny using authoritative FK binding; no fake metadata map substitutes. |
| Bad Chloe grant, human JWT or staff session | Deny unconditionally on machine boundary. |
| Valid bound subject without request proof | No AuthorizedRequestContext and no callable operation. |
| Tampered request/duplicate nonce or proof-store outage | Deny before domain operation; test actual signature library separately. |

After dependency/ciphertext review, the narrow next code proposal is typed
internal assertion/snapshot/context interfaces plus a fail-closed composer
using explicit in-process trusted test adapters, fake registry/certificate
results and the matrix above. No public route or production principal provisioning.
Only after that separate checkpoint passes should real TLS/request-proof adapters
be considered. B1.1B's existing JWT, encryption and certificate-object tests are
compatibility evidence, **not an implemented composer, trusted TLS or RFC 9421**.
DR-03/04/05/06/08 and release approval remain open.
