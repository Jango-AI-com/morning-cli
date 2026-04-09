"""Authentication primitives (token acquire/refresh/whoami + onboarding).

These live at the core layer so both the CLI and the REPL can call them
without importing Click.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from cli_anything.greeninvoice.utils.greeninvoice_backend import (
    CREDENTIALS_PATH,
    ENVIRONMENTS,
    GreenInvoiceAPIError,
    GreenInvoiceBackend,
    GreenInvoiceError,
    find_credentials,
)

# URLs pointing at the morning dashboard API-keys screen, for the wizard
# to deep-link users to the right place.
DASHBOARD_URLS = {
    "production": "https://app.greeninvoice.co.il/settings/developers/api",
    "sandbox": "https://app.sandbox.d.greeninvoice.co.il/settings/developers/api",
}


def login(session: dict[str, Any], env: str | None = None) -> dict[str, Any]:
    """Force-acquire a fresh token and cache it in ``session``."""
    backend = GreenInvoiceBackend.from_session(session, env_override=env)
    try:
        backend.acquire_token(force=True)
    finally:
        backend.close()
    return session["token"]


def logout(session: dict[str, Any]) -> None:
    """Drop the cached token (but keep api_key_id + env context)."""
    session["token"] = None


def verify_credentials(
    api_key_id: str,
    api_key_secret: str,
    env: str,
    base_url_override: str | None = None,
) -> dict[str, Any]:
    """Probe a pair of credentials against the real API.

    Returns a dict with {token, expires_at, business_name, business_id}.
    Raises ``GreenInvoiceAPIError`` on a bad key pair, or
    ``GreenInvoiceError`` on network issues / unexpected responses.
    """
    base_url = base_url_override or ENVIRONMENTS.get(env)
    if not base_url:
        raise GreenInvoiceError(f"Unknown env {env!r}")

    probe_session: dict[str, Any] = {}
    client = httpx.Client(
        timeout=30.0,
        headers={"User-Agent": "morning-cli/auth-init (+https://jango-ai.com)"},
    )
    backend = GreenInvoiceBackend(
        api_key_id=api_key_id,
        api_key_secret=api_key_secret,
        base_url=base_url,
        session=probe_session,
        client=client,
    )
    try:
        token = backend.acquire_token(force=True)
        business = backend.get("/businesses/me")
    finally:
        backend.close()

    result = {
        "token": token,
        "expires_at": probe_session["token"]["expires_at"],
        "business_name": (business or {}).get("name") if isinstance(business, dict) else None,
        "business_id": (business or {}).get("id") if isinstance(business, dict) else None,
        "base_url": base_url,
    }
    return result


def write_credentials_file(
    api_key_id: str,
    api_key_secret: str,
    env: str,
    path: Path | None = None,
) -> Path:
    """Write credentials JSON with 0600 perms. Returns the written path."""
    target = path or CREDENTIALS_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.parent.chmod(0o700)
    except PermissionError:
        pass

    payload = {"id": api_key_id, "secret": api_key_secret, "env": env}
    # Atomic-ish write: write to tmp then rename, with strict perms.
    tmp = target.with_suffix(target.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, target)
    try:
        target.chmod(0o600)
    except PermissionError:
        pass
    return target


def whoami(session: dict[str, Any]) -> dict[str, Any]:
    """Return a safe view of who we'd be acting as.

    Does not hit the network unless ``session.token`` is missing or expired —
    in which case it calls ``/businesses/me`` to verify live access.
    """
    creds = find_credentials(env_override=session.get("env"))
    info: dict[str, Any] = {
        "env": creds["env"],
        "base_url": creds["base_url"],
        "api_key_id": creds["id"],
        "token_cached": bool((session.get("token") or {}).get("value")),
        "token_expires_at": (session.get("token") or {}).get("expires_at"),
        "business_id": (session.get("context") or {}).get("business_id"),
    }
    return info
