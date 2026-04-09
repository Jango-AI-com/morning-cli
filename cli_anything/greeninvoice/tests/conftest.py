"""Shared fixtures: isolated session dir, dummy creds, tmp_dir alias."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_dir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="gi_cli_"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def isolated_session(monkeypatch, tmp_dir):
    """Redirect ~/.greeninvoice to a tmp dir and scrub credential env vars."""
    fake_home = tmp_dir / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    # Scrub any credential env vars that may leak from the real shell so
    # tests always see a pristine state.
    for leaking in (
        "MORNING_API_KEY_ID", "MORNING_API_KEY_SECRET",
        "MORNING_ENV", "MORNING_BASE_URL",
        "GREENINVOICE_API_KEY_ID", "GREENINVOICE_API_KEY_SECRET",
        "GREENINVOICE_ENV", "GREENINVOICE_BASE_URL",
    ):
        monkeypatch.delenv(leaking, raising=False)
    # Re-import session module targets to pick up the new HOME
    from cli_anything.greeninvoice.core import session as session_mod
    from cli_anything.greeninvoice.utils import greeninvoice_backend as backend_mod

    new_session_dir = fake_home / ".greeninvoice"
    new_session_path = new_session_dir / "session.json"
    new_creds_path = new_session_dir / "credentials.json"

    monkeypatch.setattr(session_mod, "SESSION_DIR", new_session_dir)
    monkeypatch.setattr(session_mod, "SESSION_PATH", new_session_path)
    monkeypatch.setattr(backend_mod, "CREDENTIALS_PATH", new_creds_path)

    yield {
        "home": fake_home,
        "dir": new_session_dir,
        "session": new_session_path,
        "creds": new_creds_path,
    }


@pytest.fixture()
def dummy_creds_env(monkeypatch):
    # Ensure we test the MORNING_* prefix path, not legacy GREENINVOICE_*.
    for legacy in (
        "GREENINVOICE_API_KEY_ID",
        "GREENINVOICE_API_KEY_SECRET",
        "GREENINVOICE_ENV",
        "GREENINVOICE_BASE_URL",
        "MORNING_BASE_URL",
    ):
        monkeypatch.delenv(legacy, raising=False)
    monkeypatch.setenv("MORNING_API_KEY_ID", "test-id")
    monkeypatch.setenv("MORNING_API_KEY_SECRET", "test-secret")
    monkeypatch.setenv("MORNING_ENV", "sandbox")
    yield
