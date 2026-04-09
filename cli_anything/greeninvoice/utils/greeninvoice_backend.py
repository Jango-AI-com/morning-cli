"""HTTP backend for the morning by Green Invoice REST API.

This module is the cli-anything "backend" — the real-software dependency per
HARNESS.md. For GUI harnesses the backend shells out to an installed binary;
here it makes authenticated HTTPS requests to the real Green Invoice API.

Responsibilities:
- Load credentials (env > credentials.json > error)
- Acquire and cache JWT tokens via ``POST /account/token``
- Transparently refresh on 401
- Decode Green Invoice error envelopes into ``GreenInvoiceAPIError``
- Handle file uploads via multipart
- Retry transient failures (429, 5xx) with exponential backoff
"""
from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any

import httpx

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

ENVIRONMENTS: dict[str, str] = {
    "production": "https://api.greeninvoice.co.il/api/v1",
    "sandbox": "https://sandbox.d.greeninvoice.co.il/api/v1",
}

DEFAULT_ENV = "sandbox"  # safe default so accidents don't hit prod
DEFAULT_TIMEOUT = 30.0   # seconds
TOKEN_SKEW_SECONDS = 60  # treat a token as expired this many seconds early
MAX_RETRIES = 3
CREDENTIALS_PATH = Path.home() / ".greeninvoice" / "credentials.json"


# -----------------------------------------------------------------------------
# Exceptions
# -----------------------------------------------------------------------------


class GreenInvoiceError(Exception):
    """Base exception for the backend."""


class CredentialsNotFoundError(GreenInvoiceError):
    """Raised when no API keys can be located (equivalent of find_binary() fail).

    The message contains install/setup instructions so agents and humans
    can self-correct. Points at the interactive wizard first.
    """

    def __init__(self) -> None:
        super().__init__(
            "morning API credentials not found.\n\n"
            "Easiest: run the interactive setup wizard\n"
            "  morning-cli auth init\n\n"
            "Or set environment variables:\n"
            "  export MORNING_API_KEY_ID=<your-key-id>\n"
            "  export MORNING_API_KEY_SECRET=<your-key-secret>\n"
            "  export MORNING_ENV=sandbox   # or 'production'\n\n"
            "(The legacy prefix GREENINVOICE_* is also supported.)\n\n"
            f"Or create {CREDENTIALS_PATH} with:\n"
            '  {"id": "...", "secret": "...", "env": "sandbox"}\n\n'
            "Generate API keys at: "
            "https://app.greeninvoice.co.il/settings/developers/api "
            "(or the sandbox equivalent)."
        )


class GreenInvoiceAPIError(GreenInvoiceError):
    """API returned a non-2xx response with a Green Invoice error envelope."""

    def __init__(
        self,
        http_status: int,
        error_code: int | None,
        message: str,
        method: str,
        path: str,
    ) -> None:
        self.http_status = http_status
        self.error_code = error_code
        self.message = message
        self.method = method
        self.path = path
        super().__init__(
            f"{method} {path} → HTTP {http_status} "
            f"(errorCode={error_code}): {message}"
        )


# -----------------------------------------------------------------------------
# Credential loading
# -----------------------------------------------------------------------------


def _env_first(*names: str) -> str | None:
    """Return the first non-empty environment variable among ``names``."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def find_credentials(env_override: str | None = None) -> dict[str, str]:
    """Return {id, secret, env, base_url} or raise ``CredentialsNotFoundError``.

    Resolution order:
    1. Environment variables — ``MORNING_*`` preferred, ``GREENINVOICE_*`` fallback
    2. ``~/.greeninvoice/credentials.json``
    """
    key_id = _env_first("MORNING_API_KEY_ID", "GREENINVOICE_API_KEY_ID")
    secret = _env_first("MORNING_API_KEY_SECRET", "GREENINVOICE_API_KEY_SECRET")
    env = (
        env_override
        or _env_first("MORNING_ENV", "GREENINVOICE_ENV")
        or DEFAULT_ENV
    )
    base_url_override = _env_first("MORNING_BASE_URL", "GREENINVOICE_BASE_URL")

    if not (key_id and secret) and CREDENTIALS_PATH.exists():
        try:
            data = json.loads(CREDENTIALS_PATH.read_text())
        except json.JSONDecodeError as exc:
            raise GreenInvoiceError(
                f"{CREDENTIALS_PATH} is not valid JSON: {exc}"
            ) from exc
        key_id = key_id or data.get("id")
        secret = secret or data.get("secret")
        env = env_override or data.get("env") or env
        base_url_override = base_url_override or data.get("base_url")

    if not (key_id and secret):
        raise CredentialsNotFoundError()

    if env not in ENVIRONMENTS and not base_url_override:
        raise GreenInvoiceError(
            f"Unknown env {env!r}; expected one of {sorted(ENVIRONMENTS)} "
            "or set GREENINVOICE_BASE_URL explicitly."
        )

    base_url = base_url_override or ENVIRONMENTS[env]
    return {"id": key_id, "secret": secret, "env": env, "base_url": base_url}


# -----------------------------------------------------------------------------
# Backend
# -----------------------------------------------------------------------------


class GreenInvoiceBackend:
    """Thin HTTP client for the morning by Green Invoice REST API.

    Usage::

        backend = GreenInvoiceBackend.from_session(session)
        clients = backend.post("/clients/search", json={"page": 1, "pageSize": 25})

    The backend mutates ``session`` in place to cache tokens. Callers are
    responsible for persisting ``session`` via ``save_session`` after use.
    """

    def __init__(
        self,
        api_key_id: str,
        api_key_secret: str,
        base_url: str,
        session: dict | None = None,
        client: httpx.Client | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.api_key_id = api_key_id
        self.api_key_secret = api_key_secret
        self.base_url = base_url.rstrip("/")
        self.session = session if session is not None else {}
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": "morning-cli/0.1 (+https://jango-ai.com; "
                "built with cli-anything)",
            },
        )

    # ---- Factory ----
    @classmethod
    def from_session(
        cls,
        session: dict,
        env_override: str | None = None,
        client: httpx.Client | None = None,
    ) -> "GreenInvoiceBackend":
        """Build a backend using credentials from env / credentials.json.

        If ``session`` has a cached token for the same ``api_key_id`` and it's
        not about to expire, reuse it.
        """
        creds = find_credentials(env_override=env_override or session.get("env"))
        session.setdefault("version", 1)
        session["env"] = creds["env"]
        session["base_url"] = creds["base_url"]
        session["api_key_id"] = creds["id"]
        return cls(
            api_key_id=creds["id"],
            api_key_secret=creds["secret"],
            base_url=creds["base_url"],
            session=session,
            client=client,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "GreenInvoiceBackend":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ---- Token management ----

    def _token_valid(self) -> bool:
        tok = self.session.get("token") or {}
        value = tok.get("value")
        expires_at = tok.get("expires_at") or 0
        return bool(value) and (expires_at - TOKEN_SKEW_SECONDS) > time.time()

    def acquire_token(self, force: bool = False) -> str:
        """Acquire (or reuse) a JWT. Returns the token string."""
        if not force and self._token_valid():
            return self.session["token"]["value"]

        url = f"{self.base_url}/account/token"
        payload = {"id": self.api_key_id, "secret": self.api_key_secret}
        resp = self._client.post(url, json=payload)
        if resp.status_code != 200:
            self._raise_api_error(resp, method="POST", path="/account/token")

        data = resp.json()
        token = data.get("token")
        expires = data.get("expires")
        if not token or not expires:
            raise GreenInvoiceError(
                f"Unexpected token response shape: {data!r}"
            )
        self.session["token"] = {"value": token, "expires_at": int(expires)}
        return token

    # ---- Request core ----

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: Any = None,
        files: dict | None = None,
        base_url: str | None = None,
        auth: bool = True,
        _retry_on_401: bool = True,
    ) -> dict | list | None:
        """Send a request and return the decoded JSON body.

        Parameters:
            base_url: override the instance base_url for this call (used for
                the Tools endpoints on ``cache.greeninvoice.co.il``).
            auth: if False, do not attach a Bearer token (for public
                Tools endpoints that don't require JWT).

        On 401 with a valid token cache, refresh once and retry (auth only).
        Retries 429/5xx up to MAX_RETRIES with exponential backoff + jitter.
        """
        effective_base = (base_url or self.base_url).rstrip("/")
        url = f"{effective_base}{path if path.startswith('/') else '/' + path}"
        headers: dict[str, str] = {}
        if auth:
            token = self.acquire_token()
            headers["Authorization"] = f"Bearer {token}"

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = self._client.request(
                    method,
                    url,
                    params=params,
                    json=json_body if files is None else None,
                    data=json_body if files is not None else None,
                    files=files,
                    headers=headers,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code == 401 and _retry_on_401 and auth:
                # Token likely expired server-side; force-refresh once.
                self.acquire_token(force=True)
                return self.request(
                    method,
                    path,
                    params=params,
                    json_body=json_body,
                    files=files,
                    base_url=base_url,
                    auth=auth,
                    _retry_on_401=False,
                )

            if resp.status_code == 429 or 500 <= resp.status_code < 600:
                # Retryable
                if attempt < MAX_RETRIES - 1:
                    self._sleep_backoff(attempt, resp)
                    continue
                self._raise_api_error(resp, method=method, path=path)

            if not (200 <= resp.status_code < 300):
                self._raise_api_error(resp, method=method, path=path)

            if not resp.content:
                return None
            try:
                return resp.json()
            except json.JSONDecodeError:
                return {"_raw": resp.text}

        raise GreenInvoiceError(
            f"Network error after {MAX_RETRIES} retries on {method} {path}: {last_exc}"
        )

    # ---- Convenience wrappers ----

    def get(
        self,
        path: str,
        params: dict | None = None,
        *,
        base_url: str | None = None,
        auth: bool = True,
    ) -> Any:
        return self.request("GET", path, params=params, base_url=base_url, auth=auth)

    def post(
        self,
        path: str,
        json: Any = None,
        files: dict | None = None,
        *,
        base_url: str | None = None,
        auth: bool = True,
    ) -> Any:
        return self.request(
            "POST", path, json_body=json, files=files, base_url=base_url, auth=auth
        )

    def put(self, path: str, json: Any = None) -> Any:
        return self.request("PUT", path, json_body=json)

    def delete(self, path: str, params: dict | None = None) -> Any:
        return self.request("DELETE", path, params=params)

    # ---- Error handling ----

    @staticmethod
    def _raise_api_error(resp: httpx.Response, *, method: str, path: str) -> None:
        code: int | None = None
        message = resp.text or resp.reason_phrase or "(no body)"
        try:
            body = resp.json()
            if isinstance(body, dict):
                code = body.get("errorCode")
                message = body.get("errorMessage", message)
        except json.JSONDecodeError:
            pass
        raise GreenInvoiceAPIError(
            http_status=resp.status_code,
            error_code=code,
            message=message,
            method=method,
            path=path,
        )

    @staticmethod
    def _sleep_backoff(attempt: int, resp: httpx.Response | None = None) -> None:
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    time.sleep(float(retry_after))
                    return
                except ValueError:
                    pass
        delay = (2 ** attempt) + random.uniform(0, 0.25)
        time.sleep(delay)
