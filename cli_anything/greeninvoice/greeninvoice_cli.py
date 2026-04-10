"""Main Click CLI for morning-cli.

Built by JangoAI with the cli-anything methodology. Implements HARNESS Phase 3:
- Click root with ``invoke_without_command=True`` → REPL is the default
- 10 command groups wiring all 66 API endpoints
- ``--json`` for machine-readable envelope output
- ``--env`` to override sandbox/production
- ``ReplSkin`` unified interactive experience
- Interactive ``auth init`` onboarding wizard
"""
from __future__ import annotations

import json
import shlex
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

import click

from cli_anything.greeninvoice import __version__
from cli_anything.greeninvoice.core import (
    auth as auth_core,
    businesses as businesses_core,
    clients as clients_core,
    documents as documents_core,
    expenses as expenses_core,
    items as items_core,
    partners as partners_core,
    payments as payments_core,
    session as session_core,
    suppliers as suppliers_core,
    tools as tools_core,
)
from cli_anything.greeninvoice.utils.greeninvoice_backend import (
    CREDENTIALS_PATH,
    ENVIRONMENTS,
    GreenInvoiceAPIError,
    GreenInvoiceBackend,
    GreenInvoiceError,
)
from cli_anything.greeninvoice.utils.repl_skin import ReplSkin

SOFTWARE_NAME = "morning-cli"
JANGOAI_CREDIT = "Built by JangoAI · https://jango-ai.com"

# -----------------------------------------------------------------------------
# Context helpers
# -----------------------------------------------------------------------------


class CLIContext:
    """Ambient state shared by all commands."""

    def __init__(self, json_mode: bool, env: str | None) -> None:
        self.json_mode = json_mode
        self.env = env
        self.session: dict[str, Any] = session_core.load_session()
        if env:
            self.session["env"] = env
        self.skin = ReplSkin(SOFTWARE_NAME, version=__version__)

    def make_backend(self) -> GreenInvoiceBackend:
        return GreenInvoiceBackend.from_session(self.session, env_override=self.env)

    def persist(self) -> None:
        session_core.save_session(self.session)


def _as_cli_context(ctx: click.Context) -> CLIContext:
    obj = ctx.ensure_object(dict)
    cli_ctx = obj.get("cli")
    if cli_ctx is None:
        cli_ctx = CLIContext(
            json_mode=obj.get("json_mode", False),
            env=obj.get("env"),
        )
        obj["cli"] = cli_ctx
    return cli_ctx


def emit(ctx: click.Context, op: str, data: Any) -> None:
    """Print a successful result in the correct output mode."""
    cli_ctx = _as_cli_context(ctx)
    if cli_ctx.json_mode:
        click.echo(
            json.dumps({"ok": True, "op": op, "data": data}, ensure_ascii=False, indent=2)
        )
    else:
        cli_ctx.skin.status("op", op)
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))


def emit_error(
    ctx: click.Context,
    op: str,
    exc: Exception,
) -> int:
    """Emit an error envelope and return the appropriate exit code."""
    cli_ctx = _as_cli_context(ctx)
    if isinstance(exc, GreenInvoiceAPIError):
        payload = {
            "code": exc.error_code,
            "message": exc.message,
            "http_status": exc.http_status,
        }
        exit_code = 3 if exc.http_status >= 500 else 2
    elif isinstance(exc, GreenInvoiceError):
        payload = {"code": None, "message": str(exc), "http_status": None}
        exit_code = 2
    else:
        payload = {"code": None, "message": f"{type(exc).__name__}: {exc}", "http_status": None}
        exit_code = 1

    if cli_ctx.json_mode:
        click.echo(
            json.dumps({"ok": False, "op": op, "error": payload}, ensure_ascii=False, indent=2),
            err=True,
        )
    else:
        cli_ctx.skin.error(f"{op}: {payload['message']}")
        if payload["code"] is not None:
            cli_ctx.skin.status("errorCode", str(payload["code"]))
        if payload["http_status"] is not None:
            cli_ctx.skin.status("HTTP", str(payload["http_status"]))
    return exit_code


def run_api(ctx: click.Context, op: str, fn: Callable[[GreenInvoiceBackend], Any]) -> None:
    """Wrap an API call: create backend, invoke, emit, persist, handle errors."""
    cli_ctx = _as_cli_context(ctx)
    try:
        with cli_ctx.make_backend() as backend:
            result = fn(backend)
        session_core.record_history(cli_ctx.session, op)
        cli_ctx.persist()
        emit(ctx, op, result)
    except Exception as exc:  # noqa: BLE001
        code = emit_error(ctx, op, exc)
        ctx.exit(code)


def load_payload(data: str | None, file: Path | None) -> dict:
    """Parse a --data '...' JSON string or --file path into a dict."""
    if data and file:
        raise click.UsageError("Use --data OR --file, not both")
    try:
        if file:
            return json.loads(Path(file).read_text())
        if data:
            return json.loads(data)
    except json.JSONDecodeError as exc:
        source = f"--file {file}" if file else "--data"
        raise click.UsageError(f"Invalid JSON in {source}: {exc}") from exc
    return {}


# -----------------------------------------------------------------------------
# Root group (REPL-by-default)
# -----------------------------------------------------------------------------


@click.group(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option("--json", "json_mode", is_flag=True, help="Machine-readable JSON envelopes.")
@click.option(
    "--env",
    type=click.Choice(["production", "sandbox"], case_sensitive=False),
    default=None,
    help="Override environment (default: sandbox, from session, or MORNING_ENV).",
)
@click.version_option(__version__, prog_name="morning-cli")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, env: str | None) -> None:
    """morning-cli — agent-native CLI for the morning invoicing REST API.

    Built by JangoAI (https://jango-ai.com) using the cli-anything methodology.
    First-time setup: run `morning-cli auth init`.
    """
    ctx.ensure_object(dict)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["env"] = env
    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


# -----------------------------------------------------------------------------
# REPL
# -----------------------------------------------------------------------------


@cli.command("repl")
@click.pass_context
def repl(ctx: click.Context) -> None:
    """Launch the interactive REPL (default behaviour)."""
    cli_ctx = _as_cli_context(ctx)
    cli_ctx.skin.print_banner()
    click.echo(f"  {JANGOAI_CREDIT}\n")
    pt_session = cli_ctx.skin.create_prompt_session()

    while True:
        try:
            line = cli_ctx.skin.get_input(
                pt_session,
                project_name=cli_ctx.session.get("env") or "?",
                modified=False,
            )
        except (EOFError, KeyboardInterrupt):
            cli_ctx.skin.print_goodbye()
            break

        line = line.strip()
        if not line:
            continue
        if line in {"exit", "quit", ":q"}:
            cli_ctx.skin.print_goodbye()
            break
        if line in {"help", "?"}:
            _repl_help(cli_ctx)
            continue

        try:
            args = shlex.split(line)
        except ValueError as exc:
            cli_ctx.skin.error(f"parse error: {exc}")
            continue

        # Re-enter the click machinery with a fresh context so each command runs
        # in isolation but shares our session object.
        try:
            with cli.make_context(
                "morning-cli",
                args,
                parent=ctx,
                info_name="morning-cli",
            ) as sub_ctx:
                sub_ctx.ensure_object(dict)
                sub_ctx.obj["cli"] = cli_ctx  # reuse same session + skin
                sub_ctx.obj["json_mode"] = cli_ctx.json_mode
                sub_ctx.obj["env"] = cli_ctx.env
                cli.invoke(sub_ctx)
        except click.exceptions.Exit:
            pass
        except click.UsageError as exc:
            cli_ctx.skin.error(str(exc))
        except Exception:  # noqa: BLE001
            cli_ctx.skin.error("unhandled exception")
            traceback.print_exc()


def _repl_help(cli_ctx: CLIContext) -> None:
    commands = {
        "auth":     "login / logout / whoami / refresh",
        "session":  "show / reset / history",
        "business": "list / get / current / update / numbering / footer / types / file-upload",
        "client":   "add / get / update / delete / search / assoc / merge / balance",
        "supplier": "add / get / update / delete / search / merge",
        "item":     "add / get / update / delete / search",
        "document": "create / preview / get / search / close / open / linked / download / info / types / statuses / templates",
        "expense":  "add / get / update / delete / search / open / close / statuses / file / draft / search-drafts",
        "payment":  "form / tokens-search / charge",
        "partner":  "users / connect / get / disconnect",
        "tools":    "occupations / countries / cities / currencies",
        "exit":     "leave the REPL",
    }
    cli_ctx.skin.help(commands)


# =============================================================================
# AUTH group
# =============================================================================


@cli.group("auth")
def auth_group() -> None:
    """Token acquisition and identity."""


@auth_group.command("login")
@click.pass_context
def auth_login(ctx: click.Context) -> None:
    """Force-acquire a fresh JWT and cache it in the session."""
    cli_ctx = _as_cli_context(ctx)
    try:
        token = auth_core.login(cli_ctx.session, env=cli_ctx.env)
        cli_ctx.persist()
        emit(ctx, "auth.login", {"expires_at": token.get("expires_at")})
    except Exception as exc:  # noqa: BLE001
        ctx.exit(emit_error(ctx, "auth.login", exc))


@auth_group.command("logout")
@click.pass_context
def auth_logout(ctx: click.Context) -> None:
    """Drop the cached token (credentials remain)."""
    cli_ctx = _as_cli_context(ctx)
    auth_core.logout(cli_ctx.session)
    cli_ctx.persist()
    emit(ctx, "auth.logout", {"token_cached": False})


@auth_group.command("whoami")
@click.pass_context
def auth_whoami(ctx: click.Context) -> None:
    """Show who the CLI would act as, based on current credentials + session."""
    cli_ctx = _as_cli_context(ctx)
    try:
        info = auth_core.whoami(cli_ctx.session)
        emit(ctx, "auth.whoami", info)
    except Exception as exc:  # noqa: BLE001
        ctx.exit(emit_error(ctx, "auth.whoami", exc))


@auth_group.command("refresh")
@click.pass_context
def auth_refresh(ctx: click.Context) -> None:
    """Alias for ``auth login``."""
    ctx.invoke(auth_login)


@auth_group.command("init")
@click.option(
    "--env",
    "env_opt",
    type=click.Choice(["production", "sandbox"], case_sensitive=False),
    default=None,
    help="Skip the env prompt and use this value.",
)
@click.option(
    "--id",
    "id_opt",
    default=None,
    help="API Key ID (skips the id prompt).",
)
@click.option(
    "--secret",
    "secret_opt",
    default=None,
    help="API Key Secret (skips the secret prompt — avoid in shell history).",
)
@click.option(
    "--credentials-file",
    "creds_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help='Read credentials from a JSON file {"id":"...","secret":"...","env":"sandbox"}.',
)
@click.option(
    "--non-interactive",
    is_flag=True,
    help="Fail instead of prompting if any value is missing.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite an existing credentials file without asking.",
)
@click.pass_context
def auth_init(
    ctx: click.Context,
    env_opt: str | None,
    id_opt: str | None,
    secret_opt: str | None,
    creds_file: Path | None,
    non_interactive: bool,
    force: bool,
) -> None:
    """Interactive setup wizard — connect your morning account.

    \b
    Walks you through:
      1. Choosing sandbox vs production
      2. Opening the morning dashboard to create API keys
      3. Entering the id + secret (secret input is hidden)
      4. Verifying them live against the real API
      5. Saving credentials to ~/.greeninvoice/credentials.json (mode 0600)

    \b
    Security options (avoid pasting secrets in chat/logs):
      --credentials-file path.json   Read keys from a file you prepare
      Environment variables           MORNING_API_KEY_ID / _SECRET

    Re-run at any time to switch environments or rotate keys.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    cli_ctx = _as_cli_context(ctx)
    json_mode = cli_ctx.json_mode
    console = Console()

    def say(text: str = "") -> None:
        if not json_mode:
            console.print(text)

    # ── Load from --credentials-file if given ──
    if creds_file:
        try:
            creds_data = json.loads(creds_file.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            raise click.UsageError(f"Cannot read credentials file: {exc}") from exc
        id_opt = id_opt or creds_data.get("id")
        secret_opt = secret_opt or creds_data.get("secret")
        env_opt = env_opt or creds_data.get("env")

    # ── Step 0: guard against accidental overwrite ──
    if CREDENTIALS_PATH.exists() and not force:
        say()
        console.print(
            f"  [yellow]![/yellow] Credentials already exist at "
            f"[dim]{CREDENTIALS_PATH}[/dim]"
        )
        if non_interactive:
            ctx.exit(emit_error(
                ctx, "auth.init",
                GreenInvoiceError(
                    f"credentials.json already exists at {CREDENTIALS_PATH}; "
                    "pass --force to overwrite."
                ),
            ))
        if not click.confirm("  Overwrite?", default=False):
            emit(ctx, "auth.init", {"cancelled": True})
            return

    # ── Banner ──
    if not json_mode:
        console.print()
        console.print(Panel(
            Text.from_markup(
                "[bold cyan]morning-cli[/bold cyan] setup wizard\n"
                "[dim]Connect your morning account in 4 steps[/dim]"
            ),
            border_style="cyan",
            padding=(1, 4),
        ))

    # ── Step 1: environment ──
    env = (env_opt or "").lower() or None
    if env is None:
        if non_interactive:
            ctx.exit(emit_error(
                ctx, "auth.init",
                GreenInvoiceError("--env is required in --non-interactive mode"),
            ))
        say()
        console.print("  [bold]Step 1/4[/bold] [dim]—[/dim] Choose environment\n")
        console.print("    [green][1][/green]  sandbox     [dim]— recommended, safe, no real money[/dim]")
        console.print("    [yellow][2][/yellow]  production  [dim]— live business data[/dim]")
        say()
        choice = click.prompt(
            "  Enter 1 or 2",
            type=click.Choice(["1", "2"], case_sensitive=False),
            default="1",
            show_default=True,
        )
        env = "sandbox" if choice == "1" else "production"

    base_url = ENVIRONMENTS[env]
    dashboard_url = auth_core.DASHBOARD_URLS[env]
    env_label = (
        "[green]sandbox[/green]" if env == "sandbox"
        else "[yellow]production[/yellow]"
    )

    if not json_mode:
        console.print(f"\n  Selected: {env_label}\n")

    # ── Step 2: point the user to the right page ──
    say()
    console.print(f"  [bold]Step 2/4[/bold] [dim]—[/dim] Get your API keys ({env})\n")
    console.print("  Open this URL in your browser and log in:\n")
    console.print(f"  [bold blue underline]{dashboard_url}[/bold blue underline]\n")
    console.print("  Navigate to: [bold]Settings > Advanced > Developers[/bold]")
    console.print("  Click [bold]\"Create API Key\"[/bold].")
    console.print("  You will see an [bold]ID[/bold] and a [bold]Secret[/bold] — "
                   "the Secret is shown [underline]once[/underline].\n")

    if not (id_opt and secret_opt):
        click.prompt("  Press Enter when ready", default="", show_default=False)

    # ── Step 3: collect credentials ──
    say()
    console.print("  [bold]Step 3/4[/bold] [dim]—[/dim] Enter your credentials\n")

    if not (id_opt and secret_opt):
        console.print("  [dim]Tip: The Secret is hidden as you type — this is normal.[/dim]")
        console.print("  [dim]Credentials are saved locally with 0600 permissions.[/dim]\n")

    api_key_id = id_opt
    api_key_secret = secret_opt
    if api_key_id is None:
        if non_interactive:
            ctx.exit(emit_error(
                ctx, "auth.init",
                GreenInvoiceError("--id is required in --non-interactive mode"),
            ))
        api_key_id = click.prompt("  API Key ID").strip()
    if api_key_secret is None:
        if non_interactive:
            ctx.exit(emit_error(
                ctx, "auth.init",
                GreenInvoiceError("--secret is required in --non-interactive mode"),
            ))
        api_key_secret = click.prompt("  API Key Secret", hide_input=True).strip()

    if not api_key_id or not api_key_secret:
        ctx.exit(emit_error(
            ctx, "auth.init",
            GreenInvoiceError("API Key ID and Secret must both be non-empty."),
        ))

    # ── Step 4: verify live ──
    say()
    console.print("  [bold]Step 4/4[/bold] [dim]—[/dim] Verifying...\n")

    try:
        info = auth_core.verify_credentials(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            env=env,
        )
    except GreenInvoiceAPIError as exc:
        code = emit_error(ctx, "auth.init", exc)
        say()
        console.print("  [red bold]Verification failed[/red bold] — credentials NOT saved.\n")
        if exc.http_status == 401:
            console.print("  [dim]Double-check the ID and Secret.[/dim]")
            console.print("  [dim]Secrets are shown only once — you may need to create a new key.[/dim]")
        elif exc.http_status == 403:
            console.print("  [dim]Your morning subscription may not include the API module.[/dim]")
            console.print("  [dim]Check your plan — 'Best' and above typically include it.[/dim]")
        ctx.exit(code)
    except Exception as exc:  # noqa: BLE001
        ctx.exit(emit_error(ctx, "auth.init", exc))

    # ── Step 5: persist ──
    try:
        written_path = auth_core.write_credentials_file(
            api_key_id=api_key_id,
            api_key_secret=api_key_secret,
            env=env,
        )
    except Exception as exc:  # noqa: BLE001
        ctx.exit(emit_error(ctx, "auth.init", exc))

    # Seed session so user can start working immediately
    cli_ctx.session["version"] = 1
    cli_ctx.session["env"] = env
    cli_ctx.session["base_url"] = base_url
    cli_ctx.session["api_key_id"] = api_key_id
    cli_ctx.session["token"] = {
        "value": info["token"],
        "expires_at": info["expires_at"],
    }
    cli_ctx.session.setdefault("context", {})["business_id"] = info.get("business_id")
    session_core.record_history(cli_ctx.session, "auth.init", env=env)
    cli_ctx.persist()

    # ── Success output ──
    if json_mode:
        emit(
            ctx,
            "auth.init",
            {
                "env": env,
                "base_url": base_url,
                "credentials_path": str(written_path),
                "business_id": info.get("business_id"),
                "business_name": info.get("business_name"),
                "token_expires_at": info["expires_at"],
            },
        )
        return

    biz_name = info.get("business_name") or "—"
    console.print(Panel(
        Text.from_markup(
            f"[green bold]Connected successfully![/green bold]\n\n"
            f"  [bold]Business:[/bold]  {biz_name}\n"
            f"  [bold]Env:[/bold]       {env}\n"
            f"  [bold]Saved to:[/bold]  [dim]{written_path}[/dim]\n\n"
            f"[dim]Try these commands:[/dim]\n"
            f"  [cyan]morning-cli[/cyan] business current\n"
            f"  [cyan]morning-cli[/cyan] --json document types\n"
            f"  [cyan]morning-cli[/cyan]                    [dim]# interactive REPL[/dim]"
        ),
        title="[bold green]All set[/bold green]",
        border_style="green",
        padding=(1, 3),
    ))
    say()


# =============================================================================
# SESSION group
# =============================================================================


@cli.group("session")
def session_group() -> None:
    """Local session state management."""


@session_group.command("show")
@click.pass_context
def session_show(ctx: click.Context) -> None:
    """Display the current session (token value redacted)."""
    cli_ctx = _as_cli_context(ctx)
    safe = json.loads(json.dumps(cli_ctx.session))  # deep copy
    tok = safe.get("token") or {}
    if tok.get("value"):
        tok["value"] = tok["value"][:12] + "…(redacted)"
    emit(ctx, "session.show", safe)


@session_group.command("reset")
@click.confirmation_option(prompt="Drop cached token and history?")
@click.pass_context
def session_reset(ctx: click.Context) -> None:
    """Reset the session file."""
    cli_ctx = _as_cli_context(ctx)
    cli_ctx.session = session_core.reset_session()
    emit(ctx, "session.reset", {"path": str(session_core.SESSION_PATH)})


@session_group.command("history")
@click.option("--limit", type=int, default=20, show_default=True)
@click.pass_context
def session_history(ctx: click.Context, limit: int) -> None:
    """Show recent mutation history."""
    cli_ctx = _as_cli_context(ctx)
    hist = (cli_ctx.session.get("history") or [])[-limit:]
    emit(ctx, "session.history", hist)


# =============================================================================
# BUSINESS group
# =============================================================================


@cli.group("business")
def business_group() -> None:
    """/businesses/* endpoints."""


@business_group.command("list")
@click.pass_context
def business_list(ctx):
    run_api(ctx, "business.list", businesses_core.list_all)


@business_group.command("current")
@click.pass_context
def business_current(ctx):
    run_api(ctx, "business.current", businesses_core.get_current)


@business_group.command("get")
@click.argument("business_id")
@click.pass_context
def business_get(ctx, business_id):
    run_api(ctx, "business.get", lambda b: businesses_core.get_by_id(b, business_id))


@business_group.command("update")
@click.option("--data", help="Raw JSON payload as a string.")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def business_update(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "business.update", lambda b: businesses_core.update(b, payload))


@business_group.command("file-upload")
@click.option("--type", "kind", required=True, help="File kind code (logo=0, signature=1, ...)")
@click.argument("file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def business_file_upload(ctx, kind, file_path):
    run_api(
        ctx,
        "business.file.upload",
        lambda b: businesses_core.upload_file(b, kind, file_path),
    )


@business_group.command("file-delete")
@click.option("--type", "kind", required=True)
@click.pass_context
def business_file_delete(ctx, kind):
    run_api(ctx, "business.file.delete", lambda b: businesses_core.delete_file(b, kind))


@business_group.command("numbering-get")
@click.pass_context
def business_numbering_get(ctx):
    run_api(ctx, "business.numbering.get", businesses_core.get_numbering)


@business_group.command("numbering-update")
@click.option("--data", help="Raw JSON payload.")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def business_numbering_update(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "business.numbering.update", lambda b: businesses_core.update_numbering(b, payload))


@business_group.command("footer")
@click.pass_context
def business_footer(ctx):
    run_api(ctx, "business.footer", businesses_core.get_footer)


@business_group.command("types")
@click.option("--lang", default="he", show_default=True)
@click.pass_context
def business_types(ctx, lang):
    run_api(ctx, "business.types", lambda b: businesses_core.get_types(b, lang))


# =============================================================================
# CLIENT group
# =============================================================================


@cli.group("client")
def client_group() -> None:
    """/clients/* endpoints."""


@client_group.command("add")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def client_add(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "client.add", lambda b: clients_core.add(b, payload))


@client_group.command("get")
@click.argument("client_id")
@click.pass_context
def client_get(ctx, client_id):
    run_api(ctx, "client.get", lambda b: clients_core.get(b, client_id))


@client_group.command("update")
@click.argument("client_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def client_update(ctx, client_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "client.update", lambda b: clients_core.update(b, client_id, payload))


@client_group.command("delete")
@click.argument("client_id")
@click.confirmation_option(prompt="Delete client?")
@click.pass_context
def client_delete(ctx, client_id):
    run_api(ctx, "client.delete", lambda b: clients_core.delete(b, client_id))


@client_group.command("search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def client_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "client.search", lambda b: clients_core.search(b, payload))


@client_group.command("assoc")
@click.argument("client_id")
@click.option("--data", required=True)
@click.pass_context
def client_assoc(ctx, client_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "client.assoc", lambda b: clients_core.assoc_documents(b, client_id, payload))


@client_group.command("merge")
@click.argument("client_id")
@click.option("--data", required=True)
@click.pass_context
def client_merge(ctx, client_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "client.merge", lambda b: clients_core.merge(b, client_id, payload))


@client_group.command("balance")
@click.argument("client_id")
@click.option("--data", required=True)
@click.pass_context
def client_balance(ctx, client_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "client.balance", lambda b: clients_core.update_balance(b, client_id, payload))


# =============================================================================
# SUPPLIER group
# =============================================================================


@cli.group("supplier")
def supplier_group() -> None:
    """/suppliers/* endpoints."""


@supplier_group.command("add")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def supplier_add(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "supplier.add", lambda b: suppliers_core.add(b, payload))


@supplier_group.command("get")
@click.argument("supplier_id")
@click.pass_context
def supplier_get(ctx, supplier_id):
    run_api(ctx, "supplier.get", lambda b: suppliers_core.get(b, supplier_id))


@supplier_group.command("update")
@click.argument("supplier_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def supplier_update(ctx, supplier_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "supplier.update", lambda b: suppliers_core.update(b, supplier_id, payload))


@supplier_group.command("delete")
@click.argument("supplier_id")
@click.confirmation_option(prompt="Delete supplier?")
@click.pass_context
def supplier_delete(ctx, supplier_id):
    run_api(ctx, "supplier.delete", lambda b: suppliers_core.delete(b, supplier_id))


@supplier_group.command("search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def supplier_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "supplier.search", lambda b: suppliers_core.search(b, payload))


@supplier_group.command("merge")
@click.argument("supplier_id")
@click.option("--data", required=True)
@click.pass_context
def supplier_merge(ctx, supplier_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "supplier.merge", lambda b: suppliers_core.merge(b, supplier_id, payload))


# =============================================================================
# ITEM group
# =============================================================================


@cli.group("item")
def item_group() -> None:
    """/items/* endpoints."""


@item_group.command("add")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def item_add(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "item.add", lambda b: items_core.add(b, payload))


@item_group.command("get")
@click.argument("item_id")
@click.pass_context
def item_get(ctx, item_id):
    run_api(ctx, "item.get", lambda b: items_core.get(b, item_id))


@item_group.command("update")
@click.argument("item_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def item_update(ctx, item_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "item.update", lambda b: items_core.update(b, item_id, payload))


@item_group.command("delete")
@click.argument("item_id")
@click.confirmation_option(prompt="Delete item?")
@click.pass_context
def item_delete(ctx, item_id):
    run_api(ctx, "item.delete", lambda b: items_core.delete(b, item_id))


@item_group.command("search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def item_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "item.search", lambda b: items_core.search(b, payload))


# =============================================================================
# DOCUMENT group
# =============================================================================


@cli.group("document")
def document_group() -> None:
    """/documents/* endpoints (invoices, receipts, quotes, ...)."""


@document_group.command("create")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_create(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "document.create", lambda b: documents_core.create(b, payload))


@document_group.command("preview")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_preview(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "document.preview", lambda b: documents_core.preview(b, payload))


@document_group.command("get")
@click.argument("document_id")
@click.pass_context
def document_get(ctx, document_id):
    run_api(ctx, "document.get", lambda b: documents_core.get(b, document_id))


@document_group.command("search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "document.search", lambda b: documents_core.search(b, payload))


@document_group.command("payments-search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_payments_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "document.payments.search", lambda b: documents_core.search_payments(b, payload))


@document_group.command("close")
@click.argument("document_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_close(ctx, document_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "document.close", lambda b: documents_core.close(b, document_id, payload))


@document_group.command("open")
@click.argument("document_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def document_open(ctx, document_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "document.open", lambda b: documents_core.open_document(b, document_id, payload))


@document_group.command("linked")
@click.argument("document_id")
@click.pass_context
def document_linked(ctx, document_id):
    run_api(ctx, "document.linked", lambda b: documents_core.linked(b, document_id))


@document_group.command("download")
@click.argument("document_id")
@click.pass_context
def document_download(ctx, document_id):
    run_api(ctx, "document.download", lambda b: documents_core.download_links(b, document_id))


@document_group.command("info")
@click.option("--type", "type_", required=True)
@click.pass_context
def document_info(ctx, type_):
    run_api(ctx, "document.info", lambda b: documents_core.info(b, type_))


@document_group.command("templates")
@click.pass_context
def document_templates(ctx):
    run_api(ctx, "document.templates", documents_core.templates)


@document_group.command("types")
@click.option("--lang", default="he", show_default=True)
@click.pass_context
def document_types(ctx, lang):
    run_api(ctx, "document.types", lambda b: documents_core.types(b, lang))


@document_group.command("statuses")
@click.option("--lang", default="he", show_default=True)
@click.pass_context
def document_statuses(ctx, lang):
    run_api(ctx, "document.statuses", lambda b: documents_core.statuses(b, lang))


# =============================================================================
# EXPENSE group
# =============================================================================


@cli.group("expense")
def expense_group() -> None:
    """/expenses/* endpoints."""


@expense_group.command("add")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def expense_add(ctx, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "expense.add", lambda b: expenses_core.add(b, payload))


@expense_group.command("get")
@click.argument("expense_id")
@click.pass_context
def expense_get(ctx, expense_id):
    run_api(ctx, "expense.get", lambda b: expenses_core.get(b, expense_id))


@expense_group.command("update")
@click.argument("expense_id")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def expense_update(ctx, expense_id, data, file):
    payload = load_payload(data, file)
    run_api(ctx, "expense.update", lambda b: expenses_core.update(b, expense_id, payload))


@expense_group.command("delete")
@click.argument("expense_id")
@click.confirmation_option(prompt="Delete expense?")
@click.pass_context
def expense_delete(ctx, expense_id):
    run_api(ctx, "expense.delete", lambda b: expenses_core.delete(b, expense_id))


@expense_group.command("search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def expense_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "expense.search", lambda b: expenses_core.search(b, payload))


@expense_group.command("open")
@click.argument("expense_id")
@click.option("--data")
@click.pass_context
def expense_open(ctx, expense_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "expense.open", lambda b: expenses_core.open_expense(b, expense_id, payload))


@expense_group.command("close")
@click.argument("expense_id")
@click.option("--data")
@click.pass_context
def expense_close(ctx, expense_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "expense.close", lambda b: expenses_core.close(b, expense_id, payload))


@expense_group.command("statuses")
@click.pass_context
def expense_statuses(ctx):
    run_api(ctx, "expense.statuses", expenses_core.statuses)


@expense_group.command("accounting-classifications")
@click.pass_context
def expense_classifications(ctx):
    run_api(ctx, "expense.classifications", expenses_core.accounting_classifications)


@expense_group.command("file-url")
@click.pass_context
def expense_file_url(ctx):
    """Step 1: get a one-time upload URL for expense files."""
    run_api(ctx, "expense.file.url", expenses_core.get_file_upload_url)


@expense_group.command("draft-from-file")
@click.option("--data", required=True)
@click.pass_context
def expense_draft_from_file(ctx, data):
    """Step 2.A: create an expense draft from an uploaded file."""
    payload = load_payload(data, None)
    run_api(ctx, "expense.draft.create", lambda b: expenses_core.create_draft_from_file(b, payload))


@expense_group.command("update-file")
@click.option("--data", required=True)
@click.pass_context
def expense_update_file(ctx, data):
    """Step 2.B: update the file on an existing draft."""
    payload = load_payload(data, None)
    run_api(ctx, "expense.draft.update", lambda b: expenses_core.update_file(b, payload))


@expense_group.command("drafts-search")
@click.option("--data")
@click.option("--file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.pass_context
def expense_drafts_search(ctx, data, file):
    payload = load_payload(data, file) or None
    run_api(ctx, "expense.drafts.search", lambda b: expenses_core.search_drafts(b, payload))


# =============================================================================
# PAYMENT group
# =============================================================================


@cli.group("payment")
def payment_group() -> None:
    """/payments/* endpoints."""


@payment_group.command("form")
@click.option("--data", required=True)
@click.pass_context
def payment_form(ctx, data):
    payload = load_payload(data, None)
    run_api(ctx, "payment.form", lambda b: payments_core.payment_form(b, payload))


@payment_group.command("tokens-search")
@click.option("--data")
@click.pass_context
def payment_tokens_search(ctx, data):
    payload = load_payload(data, None) or None
    run_api(ctx, "payment.tokens.search", lambda b: payments_core.search_tokens(b, payload))


@payment_group.command("charge")
@click.argument("token_id")
@click.option("--data", required=True)
@click.pass_context
def payment_charge(ctx, token_id, data):
    payload = load_payload(data, None)
    run_api(ctx, "payment.charge", lambda b: payments_core.charge_token(b, token_id, payload))


# =============================================================================
# PARTNER group
# =============================================================================


@cli.group("partner")
def partner_group() -> None:
    """/partners/* endpoints."""


@partner_group.command("users")
@click.pass_context
def partner_users(ctx):
    run_api(ctx, "partner.users", partners_core.list_users)


@partner_group.command("connect")
@click.option("--data", required=True)
@click.pass_context
def partner_connect(ctx, data):
    payload = load_payload(data, None)
    run_api(ctx, "partner.connect", lambda b: partners_core.request_connection(b, payload))


@partner_group.command("get")
@click.option("--email", required=True)
@click.pass_context
def partner_get(ctx, email):
    run_api(ctx, "partner.get", lambda b: partners_core.get_user(b, email))


@partner_group.command("disconnect")
@click.option("--email", required=True)
@click.confirmation_option(prompt="Disconnect partner?")
@click.pass_context
def partner_disconnect(ctx, email):
    run_api(ctx, "partner.disconnect", lambda b: partners_core.disconnect(b, email))


# =============================================================================
# TOOLS group
# =============================================================================


@cli.group("tools")
def tools_group() -> None:
    """Lookup data: occupations, countries, cities, currencies."""


@tools_group.command("occupations")
@click.option("--locale", default="he", show_default=True)
@click.pass_context
def tools_occupations(ctx, locale):
    run_api(ctx, "tools.occupations", lambda b: tools_core.occupations(b, locale))


@tools_group.command("countries")
@click.option("--locale", default="he", show_default=True)
@click.pass_context
def tools_countries(ctx, locale):
    run_api(ctx, "tools.countries", lambda b: tools_core.countries(b, locale))


@tools_group.command("cities")
@click.option("--country", required=True)
@click.option("--locale", default="he", show_default=True)
@click.pass_context
def tools_cities(ctx, country, locale):
    run_api(ctx, "tools.cities", lambda b: tools_core.cities(b, country, locale))


@tools_group.command("currencies")
@click.option("--base", default="ILS", show_default=True)
@click.pass_context
def tools_currencies(ctx, base):
    run_api(ctx, "tools.currencies", lambda b: tools_core.currencies(b, base))


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
