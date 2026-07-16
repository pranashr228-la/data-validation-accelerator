"""Configure TLS trust for corporate proxies (e.g. Zscaler MITM)."""

from __future__ import annotations

import os
from pathlib import Path


def _default_bundle_path() -> Path:
    return Path(__file__).resolve().parents[3] / "certs" / "system-ca-bundle.pem"


def configure_tls_trust(bundle_path: str | None = None) -> Path | None:
    """Point Python HTTP/SSL clients at the bundled system CA file if present.

    Respects existing ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE`` env vars.
    Uses ``DVA_CA_BUNDLE`` when set. Safe to call multiple times.
    """
    explicit = bundle_path or os.environ.get("DVA_CA_BUNDLE")
    path = Path(explicit) if explicit else _default_bundle_path()
    if not path.is_file():
        return None
    resolved = str(path.resolve())
    for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "PIP_CERT", "UV_CA_BUNDLE"):
        os.environ.setdefault(key, resolved)
    return path
