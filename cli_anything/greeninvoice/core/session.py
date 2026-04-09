"""Session persistence for morning-cli.

Implements the locked-save pattern from HARNESS ``guides/session-locking.md``:
open ``r+``, acquire exclusive ``fcntl.flock``, truncate INSIDE the lock,
rewrite, fsync, release.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

SESSION_DIR = Path.home() / ".greeninvoice"
SESSION_PATH = SESSION_DIR / "session.json"
SESSION_VERSION = 1
MAX_HISTORY = 200


def default_session() -> dict[str, Any]:
    return {
        "version": SESSION_VERSION,
        "env": None,
        "base_url": None,
        "api_key_id": None,
        "token": None,
        "context": {"business_id": None},
        "history": [],
    }


def ensure_dir(path: Path | None = None) -> None:
    """Create the session directory (uses current module SESSION_DIR)."""
    # Resolve at call time so tests can monkeypatch SESSION_DIR / SESSION_PATH.
    target_dir = path.parent if path is not None else SESSION_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        target_dir.chmod(0o700)
    except PermissionError:
        pass


def load_session(path: Path | None = None) -> dict[str, Any]:
    """Load the session file or return a fresh default."""
    if path is None:
        path = SESSION_PATH
    ensure_dir(path)
    if not path.exists():
        return default_session()
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default_session()
    if not isinstance(data, dict) or data.get("version") != SESSION_VERSION:
        # Forward-compat: start fresh on unknown version
        return default_session()
    data.setdefault("context", {"business_id": None})
    data.setdefault("history", [])
    return data


def save_session(session: dict[str, Any], path: Path | None = None) -> None:
    """Exclusive-locked save (r+ → flock → truncate → write → unlock).

    Creates the file if missing. Forces 0600 perms on creation because the
    file contains a cached JWT.
    """
    if path is None:
        path = SESSION_PATH
    ensure_dir(path)
    # Create empty file if missing so we can open r+
    if not path.exists():
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)

    # Normalize perms every save (in case umask made it wider)
    try:
        path.chmod(0o600)
    except PermissionError:
        pass

    payload = json.dumps(session, ensure_ascii=False, indent=2)
    with open(path, "r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            fh.truncate(0)
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def record_history(session: dict[str, Any], op: str, **details: Any) -> None:
    """Append an entry to session.history (trimmed to MAX_HISTORY)."""
    entry = {"ts": int(time.time()), "op": op}
    entry.update(details)
    history = session.setdefault("history", [])
    history.append(entry)
    if len(history) > MAX_HISTORY:
        del history[: len(history) - MAX_HISTORY]


def reset_session(path: Path | None = None) -> dict[str, Any]:
    """Drop cached token and history; keep no other state."""
    if path is None:
        path = SESSION_PATH
    fresh = default_session()
    save_session(fresh, path=path)
    return fresh
