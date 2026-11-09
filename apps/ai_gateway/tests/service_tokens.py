# apps/ai_gateway/tests/service_tokens.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Explicit B1.1A suite; run only in requirements.ai-gateway-b11a.txt venv.

Not named test_*.py: the baseline CI keeps its unchanged human JWT/crypto stack.
All private keys are generated in memory here and never persisted.
"""

import base64
import json
from dataclasses import FrozenInstanceError
from unittest.mock import patch
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import ec
from django.test import SimpleTestCase, override_settings
from joserfc import jws, jwt
from joserfc.jwk import ECKey, OctKey

from apps.ai_gateway.errors import GatewayDenied
from apps.ai_gateway.policy import require_metadata_permission
from apps.ai_gateway.registry import OPERATIONS
from apps.ai_gateway.security import UnavailableSecurity, VerifiedIdentity
from apps.ai_gateway.service_tokens import (
    InvalidServiceToken,
    SyntheticServiceTokenVerifier,
)

NOW = 1794009600
ORG = "11111111-1111-4111-8111-111111111111"


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


class ServiceTokenTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.private = ec.generate_private_key(ec.SECP256R1())
        cls.signer = ECKey.import_key(cls.private)
        cls.verifier = SyntheticServiceTokenVerifier(
            environment="synthetic-a", public_keys={"key-a": cls.private.public_key()}
        )

    def claims(self, **changes):
        return {
            "iss": "https://issuer.synthetic-a.example.invalid/office",
            "aud": "townlit-ai-gateway:synthetic-a",
            "sub": "office-synthetic-a-phoebe",
            "agent_id": "phoebe",
            "organization_id": ORG,
            "scopes": ["gateway.metadata"],
            "environment": "synthetic-a",
            "jti": "synthetic-token-001",
            "iat": NOW,
            "nbf": NOW,
            "exp": NOW + 300,
            **changes,
        }

    def token(self, claims=None, header=None, signer=None):
        return jwt.encode(
            {"alg": "ES256", "typ": "at+jwt", "kid": "key-a", **(header or {})},
            self.claims() if claims is None else claims,
            self.signer if signer is None else signer,
            algorithms=["ES256"],
        )

    def rejected(self, token, *, now=NOW):
        with self.assertRaisesMessage(InvalidServiceToken, "invalid_service_token"):
            self.verifier.verify(token, now=now)

    def test_valid_assertions_are_immutable_and_not_gateway_identity(self):
        token = self.token()
        claims = self.verifier.verify(token, now=NOW)
        self.assertEqual(claims.organization_reference, UUID(ORG))
        self.assertEqual(claims.scopes, frozenset({"gateway.metadata"}))
        self.assertNotIsInstance(claims, VerifiedIdentity)
        with self.assertRaises(FrozenInstanceError):
            claims.agent_id = "chloe"
        # Access-token jti is reusable, not a substitute for request proof/nonces.
        self.assertEqual(self.verifier.verify(token, now=NOW), claims)
        with override_settings(AI_GATEWAY_ENABLED=True):
            with self.assertRaises(GatewayDenied):
                require_metadata_permission(
                    claims, "gateway.capabilities", 1, UUID(ORG)
                )

    def test_exact_issuer_audience_environment(self):
        for name, values in {
            "iss": ["https://issuer.synthetic-a.example.invalid", [], "", None],
            "aud": [
                ["townlit-ai-gateway:synthetic-a"],
                ["other", "townlit-ai-gateway:synthetic-a"],
                "other",
                None,
            ],
            "environment": ["synthetic-b", "production", None, ["synthetic-a"]],
        }.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    self.rejected(self.token(self.claims(**{name: value})))
        other = SyntheticServiceTokenVerifier(
            environment="synthetic-b", public_keys={"key-a": self.private.public_key()}
        )
        with self.assertRaises(InvalidServiceToken):
            other.verify(self.token(), now=NOW)

    def test_required_and_unknown_claims(self):
        for name in self.claims():
            claims = self.claims()
            del claims[name]
            with self.subTest(missing=name):
                self.rejected(self.token(claims))
        for extra in ({"policy_version": "v1"}, {"cnf": {}}, {"is_superuser": True}):
            self.rejected(self.token(self.claims(**extra)))

    def test_claim_types_and_support_segregation(self):
        cases = {
            "sub": [None, [], 1, "", "principal with spaces", "x" * 129],
            "jti": [None, [], 1, "", "x" * 129],
            "agent_id": ["chloe", "eli", "Phoebe", [], {}, 1, None],
            "organization_id": [1, [], None, "bad", ORG.upper(), "{" + ORG + "}"],
            "scopes": [
                None,
                "gateway.metadata",
                [],
                [1],
                [{}],
                ["x", "x"],
                ["x y"],
                ["x" * 129],
                [str(x) for x in range(17)],
            ],
        }
        # ORG contains only digits; use an uppercase UUID with letters separately.
        cases["organization_id"].remove(ORG.upper())
        cases["organization_id"].append("AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA")
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    self.rejected(self.token(self.claims(**{name: value})))

    def test_dates_lifetime_and_skew_boundaries(self):
        for name in ("iat", "nbf", "exp"):
            for value in (None, True, "1794009600", NOW + 0.5, -1, 2**53):
                with self.subTest(name=name, value=value):
                    self.rejected(self.token(self.claims(**{name: value})))
        for changes in (
            {"exp": NOW + 301},
            {"exp": NOW},
            {"nbf": NOW - 1},
            {"nbf": NOW + 300},
            {"iat": NOW + 31, "nbf": NOW + 31, "exp": NOW + 300},
            {"nbf": NOW + 31},
        ):
            self.rejected(self.token(self.claims(**changes)))
        token = self.token()
        self.verifier.verify(token, now=NOW + 329)
        self.rejected(token, now=NOW + 330)
        self.verifier.verify(
            self.token(self.claims(iat=NOW + 30, nbf=NOW + 30)), now=NOW
        )
        strict = SyntheticServiceTokenVerifier(
            environment="synthetic-a",
            public_keys={"key-a": self.private.public_key()},
            clock_skew=0,
        )
        with self.assertRaises(InvalidServiceToken):
            strict.verify(self.token(self.claims(nbf=NOW + 1)), now=NOW)

    def test_key_ids_signatures_and_algorithm_confusion(self):
        self.rejected(self.token(header={"kid": "unknown"}))
        attacker = ECKey.import_key(ec.generate_private_key(ec.SECP256R1()))
        self.rejected(self.token(signer=attacker))
        for algorithm in ("HS256", "none", "RS256", "ES384", "es256"):
            header = {"alg": algorithm, "typ": "at+jwt", "kid": "key-a"}
            fake = (
                b64(json.dumps(header).encode())
                + "."
                + b64(json.dumps(self.claims()).encode())
                + "."
                + b64(bytes(64))
            )
            self.rejected(fake)
        # Real HMAC forgery using public-key bytes as the attacker-known secret.
        from cryptography.hazmat.primitives import serialization

        public_bytes = self.private.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        forged = jwt.encode(
            {"alg": "HS256", "typ": "at+jwt", "kid": "key-a"},
            self.claims(),
            OctKey(public_bytes, public_bytes),
            algorithms=["HS256"],
        )
        self.rejected(forged)
        parts = self.token().split(".")
        parts[1] = b64(json.dumps(self.claims(sub="tampered")).encode())
        self.rejected(".".join(parts))

    def test_malicious_headers_rejected_before_jose_or_network(self):
        extras = [
            {"jku": "https://attacker.invalid/jwks"},
            {"x5u": "file:///private"},
            {"jwk": {"kty": "EC"}},
            {"x5c": []},
            {"crit": ["unknown"]},
            {"b64": False},
            {"cty": "JWT"},
            {"typ": "JWT"},
            {"typ": "application/at+jwt"},
            {"kid": ["key-a"]},
        ]
        for extra in extras:
            header = {"alg": "ES256", "typ": "at+jwt", "kid": "key-a", **extra}
            token = (
                b64(json.dumps(header).encode())
                + "."
                + b64(json.dumps(self.claims()).encode())
                + "."
                + b64(bytes(64))
            )
            with (
                self.subTest(extra=extra),
                patch("apps.ai_gateway.service_tokens.jwt.decode") as decode,
            ):
                self.rejected(token)
                decode.assert_not_called()

    def test_duplicate_headers_and_signed_duplicate_claims(self):
        header, payload, signature = self.token().split(".")
        for raw in (
            b'{"alg":"HS256","alg":"ES256","typ":"at+jwt","kid":"key-a"}',
            b'{"alg":"ES256","typ":"at+jwt","kid":"unknown","k\\u0069d":"key-a"}',
        ):
            with patch("apps.ai_gateway.service_tokens.jwt.decode") as decode:
                self.rejected(b64(raw) + "." + payload + "." + signature)
                decode.assert_not_called()
        raw_claims = json.dumps(self.claims())[:-1] + ',"sub":"other"}'
        signed = jws.serialize_compact(
            {"alg": "ES256", "typ": "at+jwt", "kid": "key-a"},
            raw_claims,
            self.signer,
            algorithms=["ES256"],
        )
        self.rejected(signed)

    def test_malformed_compact_json_and_bounds(self):
        token = self.token()
        header, payload, signature = token.split(".")
        for malformed in (
            None,
            b"bytes",
            "",
            "a.b",
            token + ".extra",
            token + "!",
            token + "=",
            "x" * 8193,
            header + ".." + signature,
        ):
            self.rejected(malformed)
        for raw in (
            b"[]",
            b"null",
            b"{",
            b'"text"',
            b"\xff",
            b"\xef\xbb\xbf{}",
            b'{"exp":NaN}',
            b'{"x":' + b"[" * 1100 + b"]" * 1100 + b"}",
        ):
            self.rejected(header + "." + b64(raw) + "." + signature)
        for raw in (b"[]", b"null", b"{", b"\xff"):
            self.rejected(b64(raw) + "." + payload + "." + signature)
        self.rejected(token, now=True)

    def test_reject_bad_configuration_and_unreviewed_dependencies(self):
        for environment in ("production", "staging", "", None):
            with self.assertRaises(ValueError):
                SyntheticServiceTokenVerifier(
                    environment=environment,
                    public_keys={"k": self.private.public_key()},
                )
        for skew in (-1, 31, True, 0.5):
            with self.assertRaises(ValueError):
                SyntheticServiceTokenVerifier(
                    environment="synthetic-a",
                    public_keys={"k": self.private.public_key()},
                    clock_skew=skew,
                )
        for key in (
            self.private,
            "pem",
            ec.generate_private_key(ec.SECP384R1()).public_key(),
        ):
            with self.assertRaises(ValueError):
                SyntheticServiceTokenVerifier(
                    environment="synthetic-a", public_keys={"k": key}
                )
        with patch("apps.ai_gateway.service_tokens.version", return_value="0.0"):
            with self.assertRaises(ValueError):
                SyntheticServiceTokenVerifier(
                    environment="synthetic-a",
                    public_keys={"k": self.private.public_key()},
                )

    @override_settings(
        AI_GATEWAY_ENABLED=True,
        AI_GATEWAY_TOKEN_VERIFIER="apps.ai_gateway.service_tokens.SyntheticServiceTokenVerifier",
    )
    def test_valid_service_token_never_activates_any_public_route(self):
        token = self.token()
        self.verifier.verify(token, now=NOW)
        with patch.object(
            SyntheticServiceTokenVerifier,
            "verify",
            side_effect=AssertionError("HTTP must not invoke verifier"),
        ) as verify:
            for path in (
                "token/",
                "capabilities/",
                "accounting/vendors/",
                "advancement/opportunities/",
                "unknown/",
            ):
                response = self.client.get(
                    "/api/v1/ai-integrations/" + path,
                    HTTP_AUTHORIZATION="Bearer " + token,
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.json()["error"]["code"], "security_unavailable"
                )
                self.assertNotIn(token.encode(), response.content)
            verify.assert_not_called()
        self.assertEqual(set(OPERATIONS), {("gateway.capabilities", 1)})
        for method in ("verify", "issue"):
            with self.assertRaises(GatewayDenied):
                getattr(UnavailableSecurity(), method)(token)
