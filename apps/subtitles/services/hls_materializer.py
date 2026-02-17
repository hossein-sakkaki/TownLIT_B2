from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from urllib.parse import urlparse

from django.core.files.storage import default_storage


def _download_storage_key_to_path(storage_key: str, local_path: str) -> None:
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with default_storage.open(storage_key, "rb") as rf, open(local_path, "wb") as wf:
        while True:
            chunk = rf.read(1024 * 1024)
            if not chunk:
                break
            wf.write(chunk)


def _line_to_storage_key(line: str, base_prefix: str) -> str | None:
    """
    Convert an HLS playlist line into a storage key.
    Supports:
      - relative paths (common)
      - absolute http(s) urls (we map to url path)
    """
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return None

    if line.startswith("http://") or line.startswith("https://"):
        u = urlparse(line)
        # map "https://domain/bucket/key..." -> "bucket/key..." is NOT possible reliably.
        # but in your case URLs are typically "...amazonaws.com/<key>" so path is the key.
        return u.path.lstrip("/")

    # relative path inside same prefix
    return os.path.normpath(os.path.join(base_prefix, line)).replace("\\", "/")


@contextmanager
def materialize_hls_master_to_local(master_key: str):
    """
    Downloads:
      - master.m3u8
      - all referenced variant playlists
      - all referenced segments (.ts/.m4s/...)
    into a temp directory, preserving relative structure.

    Yields: local_master_path (string)
    """
    if not default_storage.exists(master_key):
        raise FileNotFoundError(f"HLS master missing: {master_key}")

    master_prefix = os.path.dirname(master_key).replace("\\", "/")

    with tempfile.TemporaryDirectory(prefix="hls_local_") as tmpdir:
        # 1) download master
        local_master = os.path.join(tmpdir, os.path.basename(master_key))
        _download_storage_key_to_path(master_key, local_master)

        # 2) parse master -> download variant playlists
        with open(local_master, "r", encoding="utf-8", errors="ignore") as f:
            master_lines = f.read().splitlines()

        variant_keys: list[str] = []
        for line in master_lines:
            k = _line_to_storage_key(line, master_prefix)
            if k and k.endswith(".m3u8"):
                variant_keys.append(k)

        # Download variants and their segments
        for vkey in variant_keys:
            rel = os.path.relpath(vkey, master_prefix).replace("\\", "/")
            local_variant = os.path.join(tmpdir, rel)
            _download_storage_key_to_path(vkey, local_variant)

            vprefix = os.path.dirname(vkey).replace("\\", "/")
            with open(local_variant, "r", encoding="utf-8", errors="ignore") as vf:
                vlines = vf.read().splitlines()

            for vline in vlines:
                skey = _line_to_storage_key(vline, vprefix)
                if not skey:
                    continue
                # segments can be .ts/.m4s/.aac etc. sometimes even nested playlists
                srel = os.path.relpath(skey, master_prefix).replace("\\", "/")
                local_seg = os.path.join(tmpdir, srel)
                if default_storage.exists(skey):
                    _download_storage_key_to_path(skey, local_seg)

        yield local_master
