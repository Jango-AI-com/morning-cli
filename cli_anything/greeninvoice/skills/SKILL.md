---
name: morning-cli
description: >-
  Agent-native CLI for the morning by morning REST API. 66 endpoints
  across 10 resource groups (businesses, clients, suppliers, items, documents,
  expenses, payments, partners, tools) with --json machine-readable envelopes,
  persistent session, automatic JWT refresh, sandbox-first defaults, and an
  interactive `auth init` onboarding wizard. Built by JangoAI.
---

# morning-cli

Command-line interface for **morning by morning** (Israel's leading
invoicing SaaS), built to be used by AI agents and humans alike. Wraps the
real REST API at `https://api.greeninvoice.co.il/api/v1/` — it does not
reimplement any invoice or tax logic.

Built by [JangoAI](https://jango-ai.com) with the cli-anything methodology.

## Installation

```bash
pip install morning-cli
```

**Prerequisites**
- Python 3.10+
- A morning account with API keys

## Onboarding — run the wizard first

```bash
morning-cli auth init
```

This interactive wizard:
1. Asks whether to use `sandbox` or `production`
2. Shows a deep-link to the morning API-keys page
3. Prompts for the API Key ID and Secret (secret input hidden)
4. Verifies them live against the real API
5. Saves `~/.greeninvoice/credentials.json` (mode 0600) and seeds a session

Re-run any time to switch environments or rotate keys.

For CI / agents, non-interactive mode is available:

```bash
export MORNING_API_KEY_ID=<your-key-id>
export MORNING_API_KEY_SECRET=<your-key-secret>
morning-cli auth init --env sandbox --non-interactive --force
```

Env vars — preferred prefix `MORNING_*`, legacy `GREENINVOICE_*` still supported:
- `MORNING_API_KEY_ID`
- `MORNING_API_KEY_SECRET`
- `MORNING_ENV` (`sandbox` | `production`, default `sandbox`)
- `MORNING_BASE_URL` (override for proxies / custom deploys)

## Usage modes

Two modes — REPL is the default:

```bash
morning-cli                # interactive REPL
morning-cli auth whoami    # one-shot
morning-cli --json client search   # JSON for agents
```

## JSON envelope for agents

**Always pass `--json` when calling from an agent.** Every command emits a
consistent envelope:

```json
{"ok": true, "op": "document.create", "data": {"id": "...", "number": 12345}}
```

Errors carry the morning `errorCode` and Hebrew `errorMessage`:
```json
{"ok": false, "op": "document.create", "error": {"code": 1110, "message": "מחיר לא תקין.", "http_status": 400}}
```

Exit codes: `0` ok, `1` usage/local error, `2` API error, `3` 5xx/network.

## Command groups

| Group | Purpose | Key commands |
|---|---|---|
| `auth` | Local: JWT acquire/refresh/whoami | `login`, `logout`, `whoami`, `refresh` |
| `session` | Local session state | `show`, `reset`, `history` |
| `business` | `/businesses/*` | `list`, `current`, `get`, `update`, `numbering-get`, `numbering-update`, `file-upload`, `file-delete`, `footer`, `types` |
| `client` | `/clients/*` | `add`, `get`, `update`, `delete`, `search`, `assoc`, `merge`, `balance` |
| `supplier` | `/suppliers/*` | `add`, `get`, `update`, `delete`, `search`, `merge` |
| `item` | `/items/*` | `add`, `get`, `update`, `delete`, `search` |
| `document` | `/documents/*` | `create`, `preview`, `get`, `search`, `close`, `open`, `linked`, `download`, `info`, `types`, `statuses`, `templates`, `payments-search` |
| `expense` | `/expenses/*` | `add`, `get`, `update`, `delete`, `search`, `open`, `close`, `statuses`, `accounting-classifications`, `file-url`, `draft-from-file`, `update-file`, `drafts-search` |
| `payment` | `/payments/*` | `form`, `tokens-search`, `charge` |
| `partner` | `/partners/*` | `users`, `connect`, `get`, `disconnect` |
| `tools` | Lookup data | `occupations`, `countries`, `cities`, `currencies` |

## Passing request bodies

Any command that needs a JSON body accepts either `--data '<json>'` or `--file path/to/body.json`:

```bash
morning-cli --json client add --data '{"name":"Acme","emails":["x@y.com"],"taxCode":1}'
morning-cli --json document create --file invoice.json
```

## Realistic agent workflows

### Look up the current business
```bash
morning-cli --json business current
```

### Create a tax invoice (type 305)
```bash
cat > /tmp/invoice.json <<'JSON'
{
  "description": "Monthly retainer",
  "type": 305,
  "lang": "he",
  "currency": "ILS",
  "vatType": 0,
  "client": {"name": "Acme Ltd", "emails": ["ap@acme.com"], "taxCode": 1},
  "income": [
    {"description": "Dev hours", "quantity": 10, "price": 300, "currency": "ILS", "vatType": 0}
  ]
}
JSON
morning-cli --json document create --file /tmp/invoice.json
```

### Search recent invoices
```bash
morning-cli --json document search --data '{"page":1,"pageSize":10,"type":[305]}'
```

### Get a PDF download link for a document
```bash
morning-cli --json document download <document_id>
```

## Agent guidance — read me before using

### Credential setup (IMPORTANT — read first)

**NEVER run `morning-cli auth init` through your Bash/shell tool.**
The interactive wizard asks for an API Secret — if you run it through a tool,
the secret will appear in the conversation log. The CLI detects agent
environments (CLAUDECODE, CURSOR_SESSION_ID, CODEX) and will refuse to accept
interactive secrets, showing a security notice instead.

**Instead, guide the user through these steps:**

1. Check if credentials already exist:
   ```bash
   morning-cli --json auth whoami
   ```
   If this returns `"ok": true`, credentials are configured — skip to usage.

2. If credentials are missing, tell the user:
   > Run `morning-cli auth init` in **your own terminal** (not here).
   > The wizard will walk you through creating API keys and saving them securely.
   > Once you're done, come back and I can use the CLI for you.

3. After the user confirms setup is done, verify:
   ```bash
   morning-cli --json auth whoami
   morning-cli --json business current
   ```

### Usage rules

1. **Always pass `--json`** for machine consumption. Without it the CLI prints pretty output that is harder to parse.
2. **Default env is sandbox.** To operate on real production data pass `--env production` or set `MORNING_ENV=production`.
3. **Token refresh is automatic.** On a 401 the CLI re-acquires the JWT and retries once — you don't need to handle token expiry yourself.
4. **Error codes are Hebrew.** The numeric `errorCode` is stable and agent-friendly; the `errorMessage` is for humans.
5. **Destructive commands confirm by default** (`client delete`, `supplier delete`, `item delete`, `partner disconnect`). Pass `--yes` to skip in non-interactive scripts.
6. **Document types are integers** — 305 = tax invoice, 320 = receipt, etc. Run `morning-cli --json document types` to get the full map.
7. **Documents cannot be deleted** once issued. Use drafts and `document preview` for tests.
8. **Session file lives at `~/.greeninvoice/session.json`** (mode 0600) — cached JWT and mutation history.

## Common morning error codes

| Code | Meaning |
|---|---|
| 401 | Token expired (auto-refreshed by the CLI) |
| 1003 | No active business in the account |
| 1006 | Subscription expired |
| 1007 | Missing permission |
| 1012 | Feature requires a higher plan |
| 1110 | Invalid price in a line item |
| 2002 | Wrong email or password |
| 2102 | Can't add more businesses on this plan |

## Related files

- Top-level README: [README.md](../../../README.md)
- Methodology and architecture: [GREENINVOICE.md](../../../GREENINVOICE.md)
- Full API spec (derived): [spec/api-map.json](../../../spec/api-map.json)
- Test plan and results: [tests/TEST.md](../tests/TEST.md)
