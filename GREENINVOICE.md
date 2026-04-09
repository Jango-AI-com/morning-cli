# GREENINVOICE.md — SOP for `morning-cli`

Software-specific SOP, built according to the cli-anything
[`HARNESS.md`](~/.claude/plugins/marketplaces/cli-anything/cli-anything-plugin/HARNESS.md)
methodology. Published under the `morning-cli` name on PyPI for the Israeli
developer community, by [JangoAI](https://jango-ai.com).

**Software name:** `greeninvoice` (morning by Green Invoice — Israel's leading invoicing SaaS)
**PyPI package name:** `morning-cli`
**Python namespace:** `cli_anything.greeninvoice` (kept for HARNESS / PEP 420 compat)
**Console scripts:**
- `morning-cli` — primary user-facing command
- `cli-anything-greeninvoice` — alias preserved for cli-anything methodology compat

---

## Phase 1: Backend Analysis

### 1.1 What is the "backend"?

Unlike classic cli-anything targets (GIMP, Blender, LibreOffice), the Green Invoice
"backend" is **not a local binary** — it is a hosted REST API at
`https://api.greeninvoice.co.il/api/v1/`. The `#1 HARNESS rule` ("use the real
software, don't reimplement") still applies: the CLI **must** delegate every
invoice/document/expense operation to the real API via authenticated HTTPS
requests. We do not reimplement Israeli tax logic, numbering, or PDF generation
locally — we call the API, verify the response, and surface it.

Mapping of HARNESS backend concepts:

| HARNESS (GUI app) | Green Invoice (REST) |
|---|---|
| `subprocess.run([binary, ...])` | `httpx.request(method, url, ...)` |
| Native project format (MLT, ODF, .blend) | JSON payloads + server-side state |
| `find_libreoffice()` executable lookup | Token acquisition + TTL refresh |
| Export to PDF via real renderer | `GET /documents/{id}/download/links` from real API |

### 1.2 Environments

| Env | Base URL | Use |
|---|---|---|
| Production | `https://api.greeninvoice.co.il/api/v1/` | Live business data |
| Sandbox | `https://sandbox.d.greeninvoice.co.il/api/v1/` | Testing (separate registration at `lp.sandbox.d.greeninvoice.co.il/join`) |
| Apiary mock | `https://private-anon-*-greeninvoice.apiary-mock.com/api/v1/` | Schema-level stubs, never for E2E truth |

The CLI accepts `--env {production,sandbox}` and a `--base-url` override for
custom/proxy setups. Default env is **sandbox** so accidents don't cost money.

### 1.3 Authentication

The Apiary spec leaves the `Authentication` resource group empty. The real flow
(verified live on `api.greeninvoice.co.il`) is:

1. User generates API keys in their morning account: **Settings → Advanced →
   Developers → "צור מפתח API"** → receives `id` + `secret` (shown once).
2. `POST /account/token` with JSON body `{"id": "<KEY_ID>", "secret": "<KEY_SECRET>"}`
3. Success → `{"token": "<JWT>", "expires": <unix_ts>}`. Token lifetime is
   typically 30 minutes; the `expires` field is the authoritative source of truth.
4. All other requests carry `Authorization: Bearer <token>`.
5. On 401 with `errorCode: 401` ("גישה נדחתה"), the backend transparently refreshes
   the token and retries **once**.

Credentials are loaded from environment variables (preferred) and fall back to
a `~/.greeninvoice/credentials.json` file:

```
MORNING_API_KEY_ID=...
MORNING_API_KEY_SECRET=...
MORNING_ENV=sandbox            # or production
MORNING_BASE_URL=<override>    # optional

# Legacy GREENINVOICE_* prefix is still accepted as a fallback
```

The CLI **never** logs or persists the secret. Tokens are cached in the session
file (`~/.greeninvoice/session.json`) with their expiry; the secret itself is
only read into memory when a refresh is required.

### 1.4 Data model

The Apiary spec defines **66 data structures** — the full list is dumped from
`spec/api-map.json`. The CLI does **not** reimplement them; it accepts and emits
their JSON shapes transparently. Key aggregates:

- **Business** — the current authenticated business (multi-tenant; selectable)
- **Client** / **Supplier** — contact records
- **Item** — catalog entries (products/services)
- **Document** — invoices, receipts, quotes, orders, delivery notes, credit notes
- **Expense** — purchase-side counterparts with draft workflow
- **Payment** — card tokens and charge operations
- **Partner** — cross-account connections between morning users

### 1.5 Error model

Every non-2xx response has the shape:
```json
{"errorCode": 2002, "errorMessage": "מייל או סיסמה לא נכונים."}
```
The CLI wraps this in a `GreenInvoiceAPIError` exception with the code, the
Hebrew message, and the HTTP status. JSON mode surfaces the error as
`{"ok": false, "error": {"code": ..., "message": ..., "http_status": ...}}`
with a nonzero exit code. This is the "fail loudly" rule from HARNESS.

### 1.6 Rate limiting

The Apiary description doesn't document a formal rate limit. The CLI still
respects `Retry-After` headers if present and exponentially backs off on 429.
Single-user CLI usage is well under any realistic limit.

---

## Phase 2: CLI Architecture

### 2.1 Interaction model

**Both modes, REPL is default** (per HARNESS Phase 3 rule):

- `morning-cli` → enters REPL (default behaviour)
- `morning-cli auth init` → interactive onboarding wizard
- `morning-cli client search` → one-shot subcommand
- `morning-cli --json document create ...` → machine-readable output
- The `cli-anything-greeninvoice` alias works identically (for HARNESS compat)

### 2.2 Command groups

Map directly from the 10 Apiary resource groups + `auth` + `session`:

```
morning-cli
├── auth            # (local) init (wizard), login, logout, whoami, refresh
├── session         # (local) state save/load/show/reset
├── env             # switch production/sandbox
├── business        # /businesses/*       (10 endpoints)
├── client          # /clients/*          (8)
├── supplier        # /suppliers/*        (6)
├── item            # /items/*            (5)
├── document        # /documents/*        (13)
├── expense         # /expenses/*         (13)
├── payment         # /payments/*         (3)
├── partner         # /partners/*         (4)
└── tools           # /businesses/v1/occupations, /geo-location/v1/*, /currency-exchange/v1/latest  (4)
```

**Total: 66 API endpoints + ~10 local session/auth commands.**

### 2.3 State model

State lives in `~/.greeninvoice/session.json`, written with the
`_locked_save_json` pattern from `guides/session-locking.md` (open `"r+"`, flock,
truncate inside the lock, release). Schema:

```json
{
  "version": 1,
  "env": "sandbox",
  "base_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
  "api_key_id": "abc123",
  "token": {
    "value": "eyJhbGciOi...",
    "expires_at": 1765000000
  },
  "context": {
    "business_id": "optional selected business"
  },
  "history": [
    {"ts": 1765000000, "op": "document.create", "id": "...", "notes": "invoice #5"}
  ]
}
```

Secrets: the session file contains `api_key_id` (safe-ish, identifier only)
and the short-lived `token`, but **never** the `api_key_secret`. The secret is
only read from env vars / `~/.greeninvoice/credentials.json` at token-refresh
time. File permissions set to `0600` on creation.

### 2.4 Output format

Every command supports `--json` (machine-readable envelope). Without `--json`,
the CLI uses the `ReplSkin` helpers for human-friendly tables/status lines.

Machine envelope (consistent across all commands):
```json
{
  "ok": true,
  "op": "document.create",
  "data": {"id": "65...", "number": 12345, "type": 305, "totalAmount": 1170}
}
```

Error envelope:
```json
{
  "ok": false,
  "op": "document.create",
  "error": {"code": 1110, "message": "מחיר לא תקין.", "http_status": 400}
}
```

Exit codes: `0` = ok, `1` = usage/local error, `2` = API error (non-5xx), `3` =
API 5xx / connectivity.

### 2.5 Idempotency & introspection

Per HARNESS CLI rules:

- **Introspection commands** (`business info`, `client get`, `document get`,
  `session show`, `auth whoami`) are read-only and idempotent.
- **Search commands** (`client search`, `document search`, etc.) accept
  filter flags and mirror the underlying `POST /*/search` semantics.
- **Mutation commands** (`create`, `update`, `delete`, `close`, `open`, `charge`,
  `merge`) are logged to the session `history` array for undo/reference.
- **Safe-by-default destructive ops** (`delete`, `merge`, `close`) require
  `--yes` or interactive confirmation in REPL.

### 2.6 What `greeninvoice_backend.py` looks like

The HARNESS backend module wraps the real software. Since the real software
is an HTTPS API, our backend is an `httpx.Client` wrapper that handles:

1. Base URL resolution (env/override)
2. Token acquisition + caching + automatic refresh on 401
3. Error decoding to `GreenInvoiceAPIError`
4. JSON request/response with proper Hebrew unicode handling
5. File upload multipart for `businesses/file` and `expenses/file`
6. Retry on 429/5xx with exponential backoff
7. `find_credentials()` — raises `RuntimeError` with clear instructions if API
   keys missing (equivalent of `find_libreoffice()`)

Interface (used by every `core/*.py` module):
```python
class GreenInvoiceBackend:
    def get(self, path: str, params: dict | None = None) -> dict: ...
    def post(self, path: str, json: dict | None = None, files: dict | None = None) -> dict: ...
    def put(self, path: str, json: dict | None = None) -> dict: ...
    def delete(self, path: str, params: dict | None = None) -> dict: ...
```

The core modules are thin: they map CLI args to payloads, call the backend,
and return the JSON. No business logic lives in them.

---

## Phase 3+: Implementation Plan

Follows HARNESS Phases 3–7, tracked in the TodoWrite list. Directory layout
(treating the repo root as `agent-harness/`):

```
GreeInvoice-CLI/                          # = agent-harness/
├── GREENINVOICE.md                       # this file
├── README.md                             # top-level (install + quick start)
├── setup.py                              # PEP 420 namespace package
├── pyproject.toml                        # build config
├── .env.example                          # credential template
├── spec/                                 # API spec (input)
│   ├── greeninvoice.api-elements.json    # 1.4 MB full parsed blueprint
│   ├── api-map.json                      # 124 KB compact endpoint map
│   └── api-description.html              # overview + error table
├── scripts/
│   └── extract_api_map.py                # spec → api-map.json
└── cli_anything/                         # NO __init__.py (namespace)
    └── greeninvoice/                     # HAS __init__.py
        ├── __init__.py
        ├── __main__.py
        ├── README.md
        ├── greeninvoice_cli.py           # Click group + REPL entry
        ├── core/
        │   ├── __init__.py
        │   ├── auth.py                   # token acquire/refresh/whoami
        │   ├── session.py                # locked save/load of session.json
        │   ├── businesses.py
        │   ├── clients.py
        │   ├── suppliers.py
        │   ├── items.py
        │   ├── documents.py
        │   ├── expenses.py
        │   ├── payments.py
        │   ├── partners.py
        │   └── tools.py
        ├── utils/
        │   ├── __init__.py
        │   ├── greeninvoice_backend.py   # httpx client + token mgmt
        │   └── repl_skin.py              # copied from plugin
        ├── skills/
        │   └── SKILL.md                  # Phase 6.5 output
        └── tests/
            ├── TEST.md                   # Phase 4 plan + Phase 6 results
            ├── conftest.py
            ├── test_core.py              # unit tests (mocked httpx)
            └── test_full_e2e.py          # subprocess + live sandbox API
```

The E2E test suite hits the **real sandbox API** (`sandbox.d.greeninvoice.co.il`).
CI/local runs require:
- `GREENINVOICE_SANDBOX_ID` and `GREENINVOICE_SANDBOX_SECRET` env vars
- Or the suite skips E2E tests with a clear message (but **not** the core/unit
  tests, which mock httpx)

Per HARNESS "no graceful degradation" rule, when the E2E suite is asked to run
it MUST either hit the real sandbox or fail loudly — it never silently fakes.
