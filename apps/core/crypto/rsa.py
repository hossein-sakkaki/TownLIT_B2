# apps/core/crypto/rsa.py
from __future__ import annotations
import base64
from functools import lru_cache
from typing import Optional, Union
import os, hashlib

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey, RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric import padding


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def randbytes(n: int = 32) -> bytes:
    return os.urandom(n)


# ---- Base64 helpers (استاندارد؛ در صورت نیاز urlsafe هم اضافه کن) ----
def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")

def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))

def b64e_urlsafe(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")

def b64d_urlsafe(s: str) -> bytes:
    # pad safely
    pad = '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


# ---- OAEP params (یک‌بار تعریف؛ همه‌جا همین را استفاده کن) ----
OAEP_SHA256 = padding.OAEP(
    mgf=padding.MGF1(algorithm=hashes.SHA256()),
    algorithm=hashes.SHA256(),
    label=None,
)


# ---- Key loaders ----
@lru_cache(maxsize=256)
def load_public_key_from_pem(pem_str: str) -> RSAPublicKey:
    # cryptography نسخه‌های جدید دیگه backend نمی‌خواد
    return serialization.load_pem_public_key(pem_str.encode("utf-8"))

def load_private_key_from_pem(pem_str: str, password: Optional[bytes] = None) -> RSAPrivateKey:
    return serialization.load_pem_private_key(pem_str.encode("utf-8"), password=password)


# ---- Encrypt/Decrypt helpers ----
def encrypt_with_public(
    public_key: Union[RSAPublicKey, str], plaintext: bytes
) -> bytes:
    pub: RSAPublicKey = (
        public_key if isinstance(public_key, RSAPublicKey) else load_public_key_from_pem(public_key)
    )
    return pub.encrypt(plaintext, OAEP_SHA256)

def decrypt_with_private(
    private_key: Union[RSAPrivateKey, str], ciphertext: bytes, password: Optional[bytes] = None
) -> bytes:
    priv: RSAPrivateKey
    if isinstance(private_key, RSAPrivateKey):
        priv = private_key
    else:
        priv = load_private_key_from_pem(private_key, password=password)
    return priv.decrypt(ciphertext, OAEP_SHA256)


# ---- API های صریح با نام‌های روشن (اگر ترجیح می‌دی) ----
def rsa_oaep_encrypt_with_public_pem(public_pem: str, plaintext: bytes) -> bytes:
    return encrypt_with_public(public_pem, plaintext)

def rsa_oaep_decrypt_with_private_pem(private_pem: str, ciphertext: bytes, password: Optional[bytes] = None) -> bytes:
    return decrypt_with_private(private_pem, ciphertext, password=password)

