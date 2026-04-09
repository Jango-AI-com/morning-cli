"""Unit tests — mock httpx, verify request shape, auth, session, payloads.

No network. Real API is exercised in test_full_e2e.py.
"""
from __future__ import annotations

import json
import os
import stat
import time
from pathlib import Path

import httpx
import pytest

from cli_anything.greeninvoice.core import auth as auth_core
from cli_anything.greeninvoice.core import clients as clients_core
from cli_anything.greeninvoice.core import documents as documents_core
from cli_anything.greeninvoice.core import expenses as expenses_core
from cli_anything.greeninvoice.core import partners as partners_core
from cli_anything.greeninvoice.core import session as session_core
from cli_anything.greeninvoice.core import tools as tools_core
from cli_anything.greeninvoice.greeninvoice_cli import load_payload
from cli_anything.greeninvoice.utils.greeninvoice_backend import (
    CredentialsNotFoundError,
    GreenInvoiceAPIError,
    GreenInvoiceBackend,
    GreenInvoiceError,
    find_credentials,
)


# -----------------------------------------------------------------------------
# MockTransport helpers
# -----------------------------------------------------------------------------


def make_backend(handler, *, session=None, base_url="https://sandbox.test/api/v1"):
    """Build a backend whose underlying httpx.Client uses a mock transport."""
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return GreenInvoiceBackend(
        api_key_id="test-id",
        api_key_secret="test-secret",
        base_url=base_url,
        session=session if session is not None else {},
        client=client,
    )


def ok_token_handler(jwt="jwt-abc", expires_delta=1800):
    """Returns a handler that replies to /account/token only."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/account/token")
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body == {"id": "test-id", "secret": "test-secret"}
        calls["n"] += 1
        return httpx.Response(
            200,
            json={"token": jwt, "expires": int(time.time()) + expires_delta},
        )

    return handler, calls


# =============================================================================
# Credentials
# =============================================================================


class TestFindCredentials:
    def test_from_env(self, isolated_session, dummy_creds_env):
        # Fixture order matters: isolated_session scrubs first, then
        # dummy_creds_env sets the MORNING_* env vars. Declaring them the
        # other way around would cause isolated_session to wipe what
        # dummy_creds_env just set.
        creds = find_credentials()
        assert creds["id"] == "test-id"
        assert creds["secret"] == "test-secret"
        assert creds["env"] == "sandbox"
        assert creds["base_url"].startswith("https://sandbox.d.greeninvoice")

    def test_from_file(self, monkeypatch, isolated_session):
        monkeypatch.delenv("GREENINVOICE_API_KEY_ID", raising=False)
        monkeypatch.delenv("GREENINVOICE_API_KEY_SECRET", raising=False)
        monkeypatch.delenv("GREENINVOICE_ENV", raising=False)
        monkeypatch.delenv("GREENINVOICE_BASE_URL", raising=False)
        isolated_session["dir"].mkdir(exist_ok=True)
        isolated_session["creds"].write_text(
            json.dumps({"id": "file-id", "secret": "file-secret", "env": "production"})
        )
        creds = find_credentials()
        assert creds["id"] == "file-id"
        assert creds["env"] == "production"
        assert creds["base_url"] == "https://api.greeninvoice.co.il/api/v1"

    def test_raises_when_missing(self, monkeypatch, isolated_session):
        for k in (
            "MORNING_API_KEY_ID", "MORNING_API_KEY_SECRET",
            "MORNING_ENV", "MORNING_BASE_URL",
            "GREENINVOICE_API_KEY_ID", "GREENINVOICE_API_KEY_SECRET",
            "GREENINVOICE_ENV", "GREENINVOICE_BASE_URL",
        ):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(CredentialsNotFoundError) as exc:
            find_credentials()
        msg = str(exc.value)
        # Helpful self-correct instructions for both humans and agents
        assert "morning-cli auth init" in msg  # points at wizard first
        assert "MORNING_API_KEY_ID" in msg      # new preferred env var
        assert "GREENINVOICE_" in msg            # legacy still mentioned

    def test_unknown_env(self, monkeypatch, isolated_session):
        monkeypatch.setenv("GREENINVOICE_API_KEY_ID", "x")
        monkeypatch.setenv("GREENINVOICE_API_KEY_SECRET", "y")
        monkeypatch.setenv("GREENINVOICE_ENV", "staging")
        monkeypatch.delenv("GREENINVOICE_BASE_URL", raising=False)
        with pytest.raises(GreenInvoiceError, match="Unknown env"):
            find_credentials()


# =============================================================================
# Backend — token acquisition & caching
# =============================================================================


class TestAcquireToken:
    def test_posts_creds(self):
        handler, calls = ok_token_handler()
        b = make_backend(handler)
        token = b.acquire_token()
        assert token == "jwt-abc"
        assert calls["n"] == 1
        assert b.session["token"]["value"] == "jwt-abc"
        assert b.session["token"]["expires_at"] > time.time()

    def test_caches_until_expiry(self):
        handler, calls = ok_token_handler()
        b = make_backend(handler)
        b.acquire_token()
        b.acquire_token()  # should not trigger another POST
        b.acquire_token()
        assert calls["n"] == 1

    def test_refreshes_when_expired(self):
        handler, calls = ok_token_handler()
        b = make_backend(handler)
        b.acquire_token()
        # Manually expire
        b.session["token"]["expires_at"] = int(time.time()) - 10
        b.acquire_token()
        assert calls["n"] == 2

    def test_force_refresh(self):
        handler, calls = ok_token_handler()
        b = make_backend(handler)
        b.acquire_token()
        b.acquire_token(force=True)
        assert calls["n"] == 2


# =============================================================================
# Backend — request routing, auth header, 401 retry, errors
# =============================================================================


class TestRequest:
    def test_sends_bearer_header(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/account/token"):
                return httpx.Response(
                    200, json={"token": "tok-xyz", "expires": int(time.time()) + 1800}
                )
            captured["auth"] = request.headers.get("authorization")
            captured["path"] = request.url.path
            return httpx.Response(200, json={"ok": True})

        b = make_backend(handler)
        b.get("/businesses/me")
        assert captured["auth"] == "Bearer tok-xyz"
        assert captured["path"].endswith("/businesses/me")

    def test_401_triggers_refresh_and_retry(self):
        state = {"token_calls": 0, "data_calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/account/token"):
                state["token_calls"] += 1
                return httpx.Response(
                    200,
                    json={
                        "token": f"tok-{state['token_calls']}",
                        "expires": int(time.time()) + 1800,
                    },
                )
            state["data_calls"] += 1
            if state["data_calls"] == 1:
                return httpx.Response(
                    401, json={"errorCode": 401, "errorMessage": "expired"}
                )
            return httpx.Response(200, json={"ok": True})

        b = make_backend(handler)
        result = b.get("/clients/123")
        assert result == {"ok": True}
        assert state["token_calls"] == 2  # initial + forced refresh
        assert state["data_calls"] == 2   # original + retry

    def test_raises_api_error_on_4xx(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/account/token"):
                return httpx.Response(
                    200, json={"token": "t", "expires": int(time.time()) + 1800}
                )
            return httpx.Response(
                400, json={"errorCode": 1110, "errorMessage": "מחיר לא תקין."}
            )

        b = make_backend(handler)
        with pytest.raises(GreenInvoiceAPIError) as exc:
            b.post("/documents", json={"foo": "bar"})
        assert exc.value.http_status == 400
        assert exc.value.error_code == 1110
        assert "מחיר" in exc.value.message

    def test_retries_then_raises_on_persistent_5xx(self, monkeypatch):
        # Make backoff instant so the test is fast
        import cli_anything.greeninvoice.utils.greeninvoice_backend as be
        monkeypatch.setattr(be.time, "sleep", lambda *_a, **_k: None)
        state = {"calls": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/account/token"):
                return httpx.Response(
                    200, json={"token": "t", "expires": int(time.time()) + 1800}
                )
            state["calls"] += 1
            return httpx.Response(500, json={"errorCode": 1017, "errorMessage": "שגיאה כללית"})

        b = make_backend(handler)
        with pytest.raises(GreenInvoiceAPIError):
            b.get("/clients/1")
        # MAX_RETRIES=3 attempts on the data endpoint
        assert state["calls"] == 3

    def test_empty_body_returns_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/account/token"):
                return httpx.Response(
                    200, json={"token": "t", "expires": int(time.time()) + 1800}
                )
            return httpx.Response(204)

        b = make_backend(handler)
        assert b.delete("/clients/1") is None


# =============================================================================
# session.py — persistence & perms
# =============================================================================


class TestSession:
    def test_load_default_when_missing(self, isolated_session):
        s = session_core.load_session()
        assert s["version"] == 1
        assert s["token"] is None
        assert s["history"] == []

    def test_save_and_reload_roundtrip(self, isolated_session):
        s = session_core.default_session()
        s["env"] = "sandbox"
        s["token"] = {"value": "abc", "expires_at": 123}
        session_core.save_session(s)
        reloaded = session_core.load_session()
        assert reloaded["env"] == "sandbox"
        assert reloaded["token"]["value"] == "abc"

    def test_save_sets_0600_perms(self, isolated_session):
        session_core.save_session(session_core.default_session())
        mode = stat.S_IMODE(os.stat(session_core.SESSION_PATH).st_mode)
        assert mode == 0o600

    def test_record_history_trims_to_max(self, isolated_session):
        s = session_core.default_session()
        for i in range(session_core.MAX_HISTORY + 50):
            session_core.record_history(s, f"op.{i}")
        assert len(s["history"]) == session_core.MAX_HISTORY
        # Oldest entries dropped
        assert s["history"][0]["op"] == f"op.{50}"

    def test_reset_clears_token_and_history(self, isolated_session):
        s = session_core.default_session()
        s["token"] = {"value": "x", "expires_at": 999}
        session_core.record_history(s, "foo")
        session_core.save_session(s)
        fresh = session_core.reset_session()
        assert fresh["token"] is None
        assert fresh["history"] == []


# =============================================================================
# load_payload helper
# =============================================================================


class TestLoadPayload:
    def test_from_data_string(self):
        assert load_payload('{"x": 1}', None) == {"x": 1}

    def test_from_file(self, tmp_dir):
        p = tmp_dir / "body.json"
        p.write_text('{"name": "Acme"}')
        assert load_payload(None, p) == {"name": "Acme"}

    def test_rejects_both(self, tmp_dir):
        p = tmp_dir / "body.json"
        p.write_text("{}")
        import click
        with pytest.raises(click.UsageError):
            load_payload('{"a":1}', p)

    def test_empty_when_none(self):
        assert load_payload(None, None) == {}


# =============================================================================
# Core resource modules — verify they dispatch to the right backend calls
# =============================================================================


class _FakeBackend:
    """Records method+path+kwargs for assertions."""

    def __init__(self):
        self.calls = []

    def _record(self, method, path, **kw):
        self.calls.append((method, path, kw))
        return {"fake": True}

    def get(self, path, params=None, *, base_url=None, auth=True):
        return self._record("GET", path, params=params, base_url=base_url, auth=auth)

    def post(self, path, json=None, files=None, *, base_url=None, auth=True):
        return self._record("POST", path, json=json, files=files, base_url=base_url, auth=auth)

    def put(self, path, json=None):
        return self._record("PUT", path, json=json)

    def delete(self, path, params=None):
        return self._record("DELETE", path, params=params)


class TestCoreDispatch:
    def test_clients_search_default_page(self):
        b = _FakeBackend()
        clients_core.search(b)
        assert len(b.calls) == 1
        method, path, kw = b.calls[0]
        assert (method, path) == ("POST", "/clients/search")
        assert kw["json"] == {"page": 1, "pageSize": 25}

    def test_documents_create_posts_to_root(self):
        b = _FakeBackend()
        documents_core.create(b, {"type": 305, "client": {"name": "x"}})
        method, path, kw = b.calls[0]
        assert (method, path) == ("POST", "/documents")
        assert kw["json"]["type"] == 305

    def test_tools_countries_uses_cache_host_and_normalized_locale(self):
        b = _FakeBackend()
        tools_core.countries(b, "en")
        assert len(b.calls) == 1
        method, path, kw = b.calls[0]
        assert method == "GET"
        assert path == "/geo-location/v1/countries"
        assert kw["params"] == {"locale": "en_US"}  # short code expanded
        assert kw["base_url"] == "https://cache.greeninvoice.co.il"
        assert kw["auth"] is False

    def test_expenses_file_url_get(self):
        b = _FakeBackend()
        expenses_core.get_file_upload_url(b)
        assert len(b.calls) == 1
        method, path, kw = b.calls[0]
        assert (method, path) == ("GET", "/expenses/file")
        assert kw["params"] is None

    def test_partners_disconnect_email_param(self):
        b = _FakeBackend()
        partners_core.disconnect(b, "a@b.com")
        assert b.calls == [("DELETE", "/partners/users/connection", {"params": {"email": "a@b.com"}})]


# =============================================================================
# auth.write_credentials_file — the onboarding wizard's persistence layer
# =============================================================================


class TestWriteCredentialsFile:
    def test_writes_json_with_correct_shape_and_0600(self, tmp_dir):
        target = tmp_dir / "subdir" / "credentials.json"
        auth_core.write_credentials_file(
            api_key_id="abc",
            api_key_secret="shhh",
            env="sandbox",
            path=target,
        )
        assert target.exists()
        mode = stat.S_IMODE(os.stat(target).st_mode)
        assert mode == 0o600
        data = json.loads(target.read_text())
        assert data == {"id": "abc", "secret": "shhh", "env": "sandbox"}

    def test_overwrites_existing_file(self, tmp_dir):
        target = tmp_dir / "credentials.json"
        target.write_text('{"id":"old","secret":"old","env":"production"}')
        auth_core.write_credentials_file("new", "new-secret", "sandbox", path=target)
        data = json.loads(target.read_text())
        assert data["id"] == "new"
        assert data["secret"] == "new-secret"
        assert data["env"] == "sandbox"
