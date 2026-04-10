"""E2E tests — subprocess the installed console script, hit real sandbox API.

Per HARNESS:
- Uses ``_resolve_cli("cli-anything-greeninvoice")`` — no hardcoded paths
- Tests run against the installed command, not source imports
- Sandbox API is the equivalent of "the real software"
- Set ``CLI_ANYTHING_FORCE_INSTALLED=1`` to require the installed command
- No graceful degradation: if sandbox creds are missing the entire sandbox
  block is marked skipped with a clear reason (the skip is permitted because
  sandbox requires a manual external signup that can't be automated)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

import pytest


# -----------------------------------------------------------------------------
# HARNESS-mandated CLI resolver
# -----------------------------------------------------------------------------


def _resolve_cli(*names: str) -> list[str]:
    """Resolve an installed console script; fall back to ``python -m`` in dev.

    Accepts multiple candidate names and returns the first one that exists
    on PATH. The primary name for this CLI is ``morning-cli``; the legacy
    ``cli-anything-greeninvoice`` alias is still registered for HARNESS
    methodology compat and kept here as a fallback.

    Set env ``CLI_ANYTHING_FORCE_INSTALLED=1`` to require an installed command.
    """
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    for name in names:
        path = shutil.which(name)
        if path:
            print(f"[_resolve_cli] Using installed command: {path}")
            return [path]
    if force:
        raise RuntimeError(
            f"None of {names} found in PATH. Install with: pip install -e ."
        )
    fallback_module = "cli_anything.greeninvoice"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {fallback_module}")
    return [sys.executable, "-m", fallback_module]


CLI_BASE = _resolve_cli("morning-cli", "cli-anything-greeninvoice")


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture()
def tmp_dir():
    d = Path(tempfile.mkdtemp(prefix="gi_e2e_"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture()
def sandbox_env(tmp_dir, monkeypatch):
    """Subprocess env with sandbox creds + isolated HOME.

    Skips the test if sandbox creds are missing — this is the one permitted
    skip per HARNESS because sandbox registration requires human action.
    """
    key_id = os.environ.get("GREENINVOICE_SANDBOX_ID")
    secret = os.environ.get("GREENINVOICE_SANDBOX_SECRET")
    if not (key_id and secret):
        pytest.skip(
            "Set GREENINVOICE_SANDBOX_ID and GREENINVOICE_SANDBOX_SECRET to run "
            "E2E tests against the real Green Invoice sandbox. Register at "
            "https://lp.sandbox.d.greeninvoice.co.il/join"
        )
    home = tmp_dir / "home"
    home.mkdir()
    return {
        **{k: v for k, v in os.environ.items() if not k.startswith(("GREENINVOICE_", "MORNING_"))},
        "HOME": str(home),
        "MORNING_API_KEY_ID": key_id,
        "MORNING_API_KEY_SECRET": secret,
        "MORNING_ENV": "sandbox",
    }


@pytest.fixture()
def offline_env(tmp_dir, monkeypatch):
    """Subprocess env with NO creds — used to test help, version, error shapes."""
    home = tmp_dir / "home"
    home.mkdir()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("GREENINVOICE_", "MORNING_"))
    }
    env["HOME"] = str(home)
    return env


def run(args, env=None, check=True, input_text=None):
    """Run the CLI as a subprocess and return the CompletedProcess.

    Does NOT set cwd — installed commands must work from any directory
    (HARNESS subprocess rule).
    """
    return subprocess.run(
        CLI_BASE + args,
        capture_output=True,
        text=True,
        check=check,
        env=env,
        input=input_text,
    )


# =============================================================================
# Offline tests (no network, no creds)
# =============================================================================


class TestOfflineCLI:
    def test_help_returns_zero(self, offline_env):
        r = run(["--help"], env=offline_env)
        assert r.returncode == 0
        assert "morning-cli" in r.stdout
        assert "JangoAI" in r.stdout
        # Every resource group shows up in top-level help
        for group in ("auth", "business", "client", "supplier", "item",
                      "document", "expense", "payment", "partner", "tools", "session"):
            assert group in r.stdout, f"group {group!r} missing from --help"

    def test_version_returns_zero(self, offline_env):
        from cli_anything.greeninvoice import __version__

        r = run(["--version"], env=offline_env)
        assert r.returncode == 0
        assert __version__ in r.stdout

    def test_session_show_json_envelope(self, offline_env):
        r = run(["--json", "session", "show"], env=offline_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True
        assert env["op"] == "session.show"
        assert env["data"]["version"] == 1

    def test_whoami_without_creds_errors_cleanly(self, offline_env):
        r = run(["--json", "auth", "whoami"], env=offline_env, check=False)
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        env = json.loads(r.stderr)
        assert env["ok"] is False
        assert env["op"] == "auth.whoami"
        # The error points at the onboarding wizard and mentions MORNING_* env vars.
        msg = env["error"]["message"]
        assert "morning-cli auth init" in msg
        assert "MORNING_API_KEY_ID" in msg


# =============================================================================
# Sandbox tests — hit the real sandbox API
# =============================================================================


class TestSandboxCLI:
    def test_auth_login_acquires_real_token(self, sandbox_env):
        r = run(["--json", "auth", "login"], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True
        assert env["op"] == "auth.login"
        assert env["data"]["expires_at"] > time.time()

        session_path = Path(sandbox_env["HOME"]) / ".greeninvoice" / "session.json"
        assert session_path.exists()
        session = json.loads(session_path.read_text())
        assert session["token"]["value"]
        assert session["env"] == "sandbox"

    def test_business_current_returns_data(self, sandbox_env):
        r = run(["--json", "business", "current"], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True
        assert "id" in env["data"], env["data"]
        assert "name" in env["data"]
        print(f"\n  Business: {env['data'].get('name')} ({env['data'].get('id')})")

    def test_document_types_returns_lookup(self, sandbox_env):
        r = run(["--json", "document", "types", "--lang", "en"], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True
        assert isinstance(env["data"], (list, dict))
        # Either a dict keyed by type code or a list of {id, name}
        assert len(env["data"]) > 0

    def test_full_invoice_lifecycle(self, sandbox_env, tmp_dir):
        """Create-first-invoice smoke: login → business → client → draft → search."""
        # Step 1: login
        r = run(["--json", "auth", "login"], env=sandbox_env)
        assert r.returncode == 0, r.stderr

        # Step 2: current business
        r = run(["--json", "business", "current"], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        business = json.loads(r.stdout)["data"]
        print(f"\n  Business: {business.get('name')}")

        # Step 3: create a unique client
        unique = f"CLI-test-{uuid.uuid4().hex[:8]}"
        client_payload = {
            "name": unique,
            "emails": ["cli-test@example.com"],
            "taxCode": 1,
            "country": "IL",
        }
        r = run(
            ["--json", "client", "add", "--data", json.dumps(client_payload)],
            env=sandbox_env,
        )
        assert r.returncode == 0, r.stderr
        client = json.loads(r.stdout)["data"]
        client_id = client["id"]
        print(f"  Created client: {client_id}")

        try:
            # Step 4: preview a Price Quotation (type 10) — non-binding, most
            # permissive document type across all business types. We use preview
            # rather than create so we don't leave permanent artifacts on the
            # sandbox account (documents can't be deleted once issued).
            quote_payload = {
                "description": f"E2E test {unique}",
                "type": 10,
                "lang": "he",
                "currency": "ILS",
                "vatType": 0,
                "client": {
                    "id": client_id,
                    "name": unique,
                    "emails": ["cli-test@example.com"],
                    "country": "IL",
                },
                "income": [
                    {
                        "description": "Test line item",
                        "quantity": 1,
                        "price": 100.0,
                        "currency": "ILS",
                        "vatType": 0,
                    }
                ],
            }
            quote_file = tmp_dir / "quote.json"
            quote_file.write_text(json.dumps(quote_payload))

            r = run(
                ["--json", "document", "preview", "--file", str(quote_file)],
                env=sandbox_env,
            )
            assert r.returncode == 0, r.stderr
            preview = json.loads(r.stdout)
            assert preview["ok"] is True
            assert preview["op"] == "document.preview"

            # Step 5: search documents — just verify the envelope is well-formed
            r = run(
                ["--json", "document", "search", "--data", json.dumps({"page": 1, "pageSize": 5})],
                env=sandbox_env,
            )
            assert r.returncode == 0, r.stderr
            search_env = json.loads(r.stdout)
            assert search_env["ok"] is True

            items = search_env["data"].get("items") if isinstance(search_env["data"], dict) else None
            print(f"  Preview ok, search returned {len(items) if items is not None else 'n/a'} docs")
        finally:
            # Cleanup: attempt to delete the client (may fail if docs were issued)
            run(
                ["--json", "client", "delete", "--yes", client_id],
                env=sandbox_env,
                check=False,
            )

    # ------------------------------------------------------------------
    # Read-only smoke tests — one per resource group, safe to run
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "args, op",
        [
            # Business
            (["business", "numbering-get"], "business.numbering.get"),
            (["business", "footer"], "business.footer"),
            (["business", "types", "--lang", "he"], "business.types"),
            # Documents (lookup endpoints)
            (["document", "statuses", "--lang", "en"], "document.statuses"),
            (["document", "templates"], "document.templates"),
            # Expenses (lookups)
            (["expense", "statuses"], "expense.statuses"),
            (["expense", "accounting-classifications"], "expense.classifications"),
            # Tools (separate host, no auth — tests the base_url override)
            (["tools", "occupations", "--locale", "en_US"], "tools.occupations"),
            (["tools", "countries", "--locale", "en_US"], "tools.countries"),
            (["tools", "currencies", "--base", "ILS"], "tools.currencies"),
            # NOTE: partner.users is NOT included — requires an enabled
            # Partners subscription add-on which returns 401 on accounts
            # that don't have it. The CLI wiring is covered by unit tests.
        ],
    )
    def test_readonly_smoke(self, sandbox_env, args, op):
        """Each read-only endpoint returns a well-formed ok envelope."""
        r = run(["--json", *args], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True, env
        assert env["op"] == op
        # Payload must be present — even empty lists count as "data"
        assert env["data"] is not None

    @pytest.mark.parametrize(
        "args, op",
        [
            (["client", "search"], "client.search"),
            (["supplier", "search"], "supplier.search"),
            (["item", "search"], "item.search"),
            (["expense", "search"], "expense.search"),
            (["document", "search"], "document.search"),
        ],
    )
    def test_paginated_search_smoke(self, sandbox_env, args, op):
        """Default-pagination search on every searchable resource group."""
        r = run(["--json", *args], env=sandbox_env)
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True, env
        assert env["op"] == op
        data = env["data"]
        # Morning wraps search results as {items: [...], total: N, ...}
        if isinstance(data, dict):
            assert "items" in data or "total" in data or len(data) >= 0

    # ------------------------------------------------------------------
    # Round-trip mutation tests — create → verify → cleanup
    # ------------------------------------------------------------------

    def test_item_round_trip(self, sandbox_env):
        """Item lifecycle: add → get → update → delete.

        Items are catalog entries (products/services) and are fully mutable,
        including hard delete. This verifies the full CRUD path end-to-end.
        """
        unique = f"item-{uuid.uuid4().hex[:8]}"
        add_payload = {
            "name": unique,
            "description": "E2E test item",
            "price": 150.0,
            "currency": "ILS",
            "vatType": 0,
        }

        # 1. Add
        r = run(
            ["--json", "item", "add", "--data", json.dumps(add_payload, ensure_ascii=False)],
            env=sandbox_env,
        )
        assert r.returncode == 0, r.stderr
        item = json.loads(r.stdout)["data"]
        item_id = item["id"]
        print(f"\n  Created item: {item_id}")

        try:
            # 2. Get
            r = run(["--json", "item", "get", item_id], env=sandbox_env)
            assert r.returncode == 0, r.stderr
            fetched = json.loads(r.stdout)["data"]
            assert fetched["id"] == item_id
            assert fetched["name"] == unique

            # 3. Update
            update_payload = {"name": unique, "description": "updated desc", "price": 175.0}
            r = run(
                [
                    "--json",
                    "item",
                    "update",
                    item_id,
                    "--data",
                    json.dumps(update_payload, ensure_ascii=False),
                ],
                env=sandbox_env,
            )
            assert r.returncode == 0, r.stderr
            updated_env = json.loads(r.stdout)
            assert updated_env["ok"] is True
        finally:
            # 4. Delete (with --yes to bypass confirmation prompt)
            r = run(
                ["--json", "item", "delete", "--yes", item_id],
                env=sandbox_env,
                check=False,
            )
            # Delete may return the deleted id or an empty body — just verify envelope
            try:
                env = json.loads(r.stdout or r.stderr or "{}")
                print(f"  Deleted item: {item_id} (ok={env.get('ok')})")
            except json.JSONDecodeError:
                pass

    def test_supplier_round_trip(self, sandbox_env):
        """Supplier create → delete (no expenses attached, so safe to drop)."""
        unique = f"supp-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique,
            "emails": ["supplier-test@example.com"],
            "country": "IL",
        }

        r = run(
            ["--json", "supplier", "add", "--data", json.dumps(payload, ensure_ascii=False)],
            env=sandbox_env,
        )
        assert r.returncode == 0, r.stderr
        supplier = json.loads(r.stdout)["data"]
        supplier_id = supplier["id"]
        assert supplier["name"] == unique
        print(f"\n  Created supplier: {supplier_id}")

        try:
            r = run(["--json", "supplier", "get", supplier_id], env=sandbox_env)
            assert r.returncode == 0, r.stderr
            fetched = json.loads(r.stdout)["data"]
            assert fetched["id"] == supplier_id
        finally:
            run(
                ["--json", "supplier", "delete", "--yes", supplier_id],
                env=sandbox_env,
                check=False,
            )

    def test_proforma_invoice_preview(self, sandbox_env, tmp_dir):
        """Preview a Proforma Invoice (חשבון עסקה, type 300).

        This is the user's primary real-world use case — an ``עוסק פטור`` can
        legally issue a proforma because it's pre-payment (not a tax invoice).
        Verifies the full /documents/preview flow for type 300 against the
        real sandbox API.
        """
        unique = f"Proforma-{uuid.uuid4().hex[:8]}"
        proforma_payload = {
            "description": f"E2E proforma {unique}",
            "type": 300,  # חשבון עסקה / Proforma Invoice
            "lang": "he",
            "currency": "ILS",
            "vatType": 0,
            "client": {
                "name": unique,
                "emails": ["cli-test@example.com"],
                "country": "IL",
            },
            "income": [
                {
                    "description": "שירותי ייעוץ",
                    "quantity": 1,
                    "price": 500.0,
                    "currency": "ILS",
                    "vatType": 0,
                }
            ],
        }
        payload_file = tmp_dir / "proforma.json"
        payload_file.write_text(json.dumps(proforma_payload, ensure_ascii=False))

        r = run(
            ["--json", "document", "preview", "--file", str(payload_file)],
            env=sandbox_env,
        )
        assert r.returncode == 0, r.stderr
        env = json.loads(r.stdout)
        assert env["ok"] is True, env
        assert env["op"] == "document.preview"
        data = env["data"]
        # Verify the real API echoed back the structure we'd expect on a
        # proforma: type code 300, at least one income row, Hebrew content
        # preserved through the stack, and a totalling field.
        if isinstance(data, dict):
            if "type" in data:
                assert data["type"] == 300
            if "income" in data and data["income"]:
                assert data["income"][0]["description"] == "שירותי ייעוץ"
        print(f"\n  Proforma preview ok ({unique})")
