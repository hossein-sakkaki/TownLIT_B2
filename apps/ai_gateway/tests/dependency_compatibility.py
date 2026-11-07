# apps/ai_gateway/tests/dependency_compatibility.py
# TownLIT-Backend
#
# Created by Hossein Sakkaki on 2026-11-06.
# Last Update by Hossein Sakkaki on 2026-11-06.
#

"""Explicit disposable dependency-matrix smoke checks, never production setup.

Full Backend human/session/reset regressions run separately in each CI profile.
The committed ciphertext is public synthetic data generated with the baseline.
"""

import base64
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from django.db import connection, models
from django.test import SimpleTestCase
from django_cryptography.fields import encrypt
from OpenSSL import crypto


class DependencyCompatibilityTests(SimpleTestCase):
    def test_pyjwt_hmac_roundtrip_and_tampering(self):
        # Representative library compatibility; not a new human-token policy.
        key = "b11b-public-synthetic-hmac-key-000000000000"
        token = jwt.encode(
            {"sub": "synthetic", "exp": 4102444800}, key, algorithm="HS256"
        )
        self.assertEqual(
            jwt.decode(token, key, algorithms=["HS256"])["sub"], "synthetic"
        )
        with self.assertRaises(jwt.InvalidSignatureError):
            jwt.decode(token, key + "other", algorithms=["HS256"])
        with self.assertRaises(jwt.InvalidAlgorithmError):
            jwt.decode(token, key, algorithms=["ES256"])

    def test_encrypted_field_reads_baseline_ciphertext_and_roundtrips(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/b11b_ciphertext.json").read_text()
        )
        field = encrypt(models.TextField(), key=b"0" * 32)
        field.set_attributes_from_name("synthetic")
        self.assertEqual(
            field.from_db_value(
                base64.b64decode(fixture["field_ciphertext"]), None, connection
            ),
            fixture["value"],
        )
        for value in ("", "café", "synthetic " * 1024, None):
            prepared = field.get_db_prep_value(value, connection)
            self.assertEqual(field.from_db_value(prepared, None, connection), value)

    def test_fernet_reads_baseline_ciphertext_rejects_wrong_key(self):
        fixture = json.loads(
            (Path(__file__).parent / "fixtures/b11b_ciphertext.json").read_text()
        )
        cipher = Fernet(base64.urlsafe_b64encode(b"0" * 32))
        self.assertEqual(
            cipher.decrypt(fixture["fernet_ciphertext"].encode()).decode(),
            fixture["value"],
        )
        with self.assertRaises(InvalidToken):
            Fernet(base64.urlsafe_b64encode(b"1" * 32)).decrypt(
                fixture["fernet_ciphertext"].encode()
            )
        value = cipher.encrypt(b"synthetic")
        self.assertEqual(cipher.decrypt(value), b"synthetic")

    def test_pyopenssl_cryptography_certificate_interop(self):
        # Ephemeral self-signed object interop only; no TLS handshake or trust.
        private = ec.generate_private_key(ec.SECP256R1())
        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "synthetic.invalid")]
        )
        now = datetime.now(timezone.utc)
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(subject)
            .public_key(private.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(minutes=5))
            .sign(private, hashes.SHA256())
        )
        converted = crypto.X509.from_cryptography(cert).to_cryptography()
        self.assertEqual(
            converted.fingerprint(hashes.SHA256()), cert.fingerprint(hashes.SHA256())
        )
        self.assertEqual(len(cert.fingerprint(hashes.SHA256())), 32)
