# morning-cli

**Agent-native command-line interface for [morning by Green Invoice](https://www.greeninvoice.co.il) — Israel's leading invoicing SaaS.**

Built by [JangoAI](https://jango-ai.com) using the [cli-anything](https://github.com/HKUDS/CLI-Anything) methodology. Hebrew README: [README.he.md](README.he.md).

- **66 endpoints** across 10 resource groups (Businesses, Clients, Suppliers, Items, Documents, Expenses, Payments, Partners, Tools)
- **Interactive setup wizard** — `morning-cli auth init` walks you through API key creation
- **REPL** as the default mode — run `morning-cli` with no args
- **`--json` envelopes** for AI-agent consumption — stable shape, documented error codes
- **Automatic JWT refresh** on 401, with transparent retry
- **Sandbox-first** — default environment is sandbox so accidents don't touch production
- **Locked session file** at `~/.greeninvoice/session.json` (mode 0600)
- **55 tests**, including 22 end-to-end against the real sandbox API
- **Hebrew error messages** preserved end-to-end

## Install

```bash
pip install morning-cli
```

Python 3.10+ required.

## Quick start

```bash
# 1. Run the interactive onboarding wizard
morning-cli auth init

# 2. Try the REPL
morning-cli

# Or use one-shot commands
morning-cli --json business current
morning-cli --json document types --lang he
morning-cli --json client search
```

### What `auth init` does

```
 morning-cli setup wizard
 ──────────────────────────

 Step 1/4 — choose environment
   sandbox    (recommended — safe, no real money)
   production (live data)
   env [sandbox]:

 Step 2/4 — get your API keys (sandbox)
   Open this URL in your browser and log in:

     https://app.sandbox.d.greeninvoice.co.il/settings/developers/api

   Then: Settings → Advanced → Developers → 'יצירת מפתח API'
   Copy the ID and the Secret. The Secret is shown ONCE — save it now.

 Step 3/4 — paste your credentials
   API Key ID:     xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   API Key Secret: ●●●●●●●●●●●●●●●●●●●●●●●●●●●●

 Step 4/4 — verifying against the real API...
   ✓ Authenticated successfully
   business:    Your Business Name
   business_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   env:         sandbox
   saved to:    ~/.greeninvoice/credentials.json

   All set. Try:
     morning-cli business current
     morning-cli --json document types --lang he
     morning-cli                      # interactive REPL
```

The wizard saves your keys to `~/.greeninvoice/credentials.json` (mode 0600) and verifies them live before writing anything.

### Non-interactive setup (for scripts and CI)

```bash
export MORNING_API_KEY_ID=<your-id>
export MORNING_API_KEY_SECRET=<your-secret>
export MORNING_ENV=sandbox          # or production
morning-cli auth init --non-interactive --force
```

The legacy prefix `GREENINVOICE_*` is also supported for backwards compatibility.

## Commands

| Group | Endpoints | Key commands |
|---|---|---|
| `auth` | local | `init` (wizard), `login`, `logout`, `whoami`, `refresh` |
| `session` | local | `show`, `reset`, `history` |
| `business` | 10 | `list`, `current`, `get`, `update`, `numbering-get`, `numbering-update`, `file-upload`, `file-delete`, `footer`, `types` |
| `client` | 8 | `add`, `get`, `update`, `delete`, `search`, `assoc`, `merge`, `balance` |
| `supplier` | 6 | `add`, `get`, `update`, `delete`, `search`, `merge` |
| `item` | 5 | `add`, `get`, `update`, `delete`, `search` |
| `document` | 13 | `create`, `preview`, `get`, `search`, `close`, `open`, `linked`, `download`, `info`, `types`, `statuses`, `templates`, `payments-search` |
| `expense` | 13 | `add`, `get`, `update`, `delete`, `search`, `open`, `close`, `statuses`, `accounting-classifications`, `file-url`, `draft-from-file`, `update-file`, `drafts-search` |
| `payment` | 3 | `form`, `tokens-search`, `charge` |
| `partner` | 4 | `users`, `connect`, `get`, `disconnect` |
| `tools` | 4 | `occupations`, `countries`, `cities`, `currencies` |

### Passing JSON bodies

Any command that needs a request body accepts either `--data '<json>'` or `--file path/to/body.json`:

```bash
morning-cli --json client add --data '{"name":"Acme","emails":["x@y.com"],"taxCode":1}'
morning-cli --json document create --file invoice.json
```

### Example — create a proforma invoice (חשבון עסקה)

```bash
cat > /tmp/proforma.json <<'JSON'
{
  "description": "Monthly retainer",
  "type": 300,
  "lang": "he",
  "currency": "ILS",
  "vatType": 0,
  "client": {"name": "Acme Ltd", "emails": ["ap@acme.com"], "country": "IL"},
  "income": [
    {"description": "שירותי ייעוץ", "quantity": 10, "price": 300, "currency": "ILS", "vatType": 0}
  ]
}
JSON
morning-cli --json document preview --file /tmp/proforma.json
morning-cli --json document create --file /tmp/proforma.json
```

## Output envelope (for agents)

Every `--json` command returns a consistent envelope:

```json
{"ok": true, "op": "document.create", "data": {"id": "...", "number": 12345}}
```

Errors carry the Green Invoice `errorCode` and the (Hebrew) `errorMessage`:

```json
{"ok": false, "op": "document.create", "error": {"code": 1110, "message": "מחיר לא תקין.", "http_status": 400}}
```

**Exit codes:** `0` ok · `1` usage/local error · `2` API error · `3` 5xx/network

## Environment variables

| Variable | Purpose |
|---|---|
| `MORNING_API_KEY_ID` | API key ID (fallback: `GREENINVOICE_API_KEY_ID`) |
| `MORNING_API_KEY_SECRET` | API key secret (fallback: `GREENINVOICE_API_KEY_SECRET`) |
| `MORNING_ENV` | `sandbox` or `production` (fallback: `GREENINVOICE_ENV`, default `sandbox`) |
| `MORNING_BASE_URL` | Override base URL entirely (proxies, custom deploys) |

## Tests

```bash
pip install -e ".[test]"

# Unit tests — no network
pytest cli_anything/greeninvoice/tests/test_core.py -v

# Full suite including live sandbox E2E
export MORNING_SANDBOX_ID=<your-sandbox-id>
export MORNING_SANDBOX_SECRET=<your-sandbox-secret>
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/greeninvoice/tests/ -v
```

**55 tests** — 27 unit tests (mock `httpx`) + 4 offline E2E (help, version, error envelopes) + 22 live sandbox E2E (auth, business, documents, items, suppliers, expenses, tools, read-only smoke across all 10 resource groups). See [tests/TEST.md](cli_anything/greeninvoice/tests/TEST.md) for the full plan and results.

## Methodology

Built with the cli-anything 7-phase SOP:

1. **Codebase analysis** — parsed Apiary spec → 66 endpoints mapped
2. **Architecture** — 10 resource groups + local auth/session, REPL-first
3. **Implementation** — Python namespace package `cli_anything.greeninvoice`
4. **Test planning** — `tests/TEST.md`
5. **Test implementation** — unit + live E2E
6. **Test documentation** — results captured
7. **PyPI publishing** — `pip install morning-cli`

Full methodology in [GREENINVOICE.md](GREENINVOICE.md).

## For AI agents

`morning-cli` ships with a [SKILL.md](cli_anything/greeninvoice/skills/SKILL.md) file that's auto-discovered by the REPL banner and Claude Code / Cursor. If you're an agent reading this, check the skill file first — it has concrete invocation examples and Green Invoice error code references.

## Contributing

PRs welcome at [github.com/jango-ai-com/morning-cli](https://github.com/jango-ai-com/morning-cli). Run the tests before submitting:

```bash
pip install -e ".[test]"
pytest cli_anything/greeninvoice/tests/test_core.py -v
```

## About JangoAI

[JangoAI](https://jango-ai.com) is an Israeli AI automation studio. We build agent-native tooling for Israeli developers and businesses — n8n workflows, Monday.com integrations, Supabase data models, and CLIs like this one.

## License

MIT. See [LICENSE](LICENSE).

---

*Created by JangoAI · [jango-ai.com](https://jango-ai.com) · [@jango-ai-com on GitHub](https://github.com/jango-ai-com)*
