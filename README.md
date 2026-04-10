<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,50:7c3aed,100:06b6d4&height=220&section=header&text=morning-cli&fontSize=70&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Agent-native%20CLI%20for%20the%20morning%20invoicing%20API&descSize=18&descAlignY=55&descAlign=50" alt="morning-cli banner" width="100%"/>
</p>

<p align="center">
  <a href="https://pypi.org/project/morning-cli/"><img src="https://img.shields.io/pypi/v/morning-cli?style=for-the-badge&logo=pypi&logoColor=white&label=PyPI&color=3775A9" alt="PyPI version"/></a>
  <a href="https://pypi.org/project/morning-cli/"><img src="https://img.shields.io/pypi/pyversions/morning-cli?style=for-the-badge&logo=python&logoColor=white&color=3776AB" alt="Python versions"/></a>
  <a href="https://github.com/Jango-AI-com/morning-cli/actions"><img src="https://img.shields.io/github/actions/workflow/status/Jango-AI-com/morning-cli/ci.yml?style=for-the-badge&logo=github-actions&logoColor=white&label=CI" alt="CI status"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/Jango-AI-com/morning-cli?style=for-the-badge&color=22c55e" alt="License"/></a>
  <a href="https://pypi.org/project/morning-cli/"><img src="https://img.shields.io/pypi/dm/morning-cli?style=for-the-badge&logo=pypi&logoColor=white&color=blueviolet&label=downloads" alt="Downloads"/></a>
</p>

<p align="center">
  <b>66 endpoints</b> &nbsp;|&nbsp; <b>Interactive REPL</b> &nbsp;|&nbsp; <b>Onboarding wizard</b> &nbsp;|&nbsp; <b>JSON envelopes for AI agents</b> &nbsp;|&nbsp; <b>Hebrew error messages</b>
</p>

<p align="center">
  <sub>Built by <a href="https://jango-ai.com"><b>JangoAI</b></a> using the <a href="https://github.com/HKUDS/CLI-Anything">cli-anything</a> methodology &nbsp;|&nbsp; <a href="README.he.md">README בעברית</a></sub>
</p>

---

## Why this exists

I'm Maor, a solo developer running [JangoAI](https://jango-ai.com) — a small AI automation studio in Israel. I use morning's API daily for my own business and my clients', and I got tired of writing the same `httpx` + JWT boilerplate in every project. So I built a proper CLI around it.

This started as a personal tool, but there's no reason to keep it private — if you work with morning's API, you'll save time with this. I'm sharing it with the Israeli dev community because I think we deserve better tooling for our local platforms. If it helps you, I'd love to hear about it.

---

## Install

```bash
pip install morning-cli
```

## Get started in 30 seconds

```bash
# 1. Run the interactive wizard — connects your morning account
morning-cli auth init

# 2. Start the REPL
morning-cli

# 3. Or use one-shot commands
morning-cli --json business current
morning-cli --json document types --lang he
morning-cli --json client search
```

<details>
<summary><b>What does <code>auth init</code> look like?</b></summary>

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

  Step 3/4 — paste your credentials
    API Key ID:     xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    API Key Secret: ●●●●●●●●●●●●●●●●●●●●●●●●●●●●

  Step 4/4 — verifying against the real API...
    ✓ Authenticated successfully
    business:    Your Business Name
    env:         sandbox
    saved to:    ~/.greeninvoice/credentials.json

    All set. Try:
      morning-cli business current
      morning-cli --json document types --lang he
      morning-cli                      # interactive REPL
```

</details>

---

## Commands

<table>
<tr>
<th>Group</th>
<th>Endpoints</th>
<th>Highlights</th>
</tr>
<tr><td><b>auth</b></td><td>local</td><td><code>init</code> (wizard), <code>login</code>, <code>logout</code>, <code>whoami</code>, <code>refresh</code></td></tr>
<tr><td><b>session</b></td><td>local</td><td><code>show</code>, <code>reset</code>, <code>history</code></td></tr>
<tr><td><b>business</b></td><td>10</td><td><code>list</code>, <code>current</code>, <code>get</code>, <code>update</code>, numbering, footer, types, file-upload</td></tr>
<tr><td><b>client</b></td><td>8</td><td><code>add</code>, <code>get</code>, <code>update</code>, <code>delete</code>, <code>search</code>, <code>assoc</code>, <code>merge</code>, <code>balance</code></td></tr>
<tr><td><b>supplier</b></td><td>6</td><td><code>add</code>, <code>get</code>, <code>update</code>, <code>delete</code>, <code>search</code>, <code>merge</code></td></tr>
<tr><td><b>item</b></td><td>5</td><td><code>add</code>, <code>get</code>, <code>update</code>, <code>delete</code>, <code>search</code></td></tr>
<tr><td><b>document</b></td><td>13</td><td><code>create</code>, <code>preview</code>, <code>get</code>, <code>search</code>, <code>close</code>, <code>open</code>, <code>download</code>, types, statuses</td></tr>
<tr><td><b>expense</b></td><td>13</td><td>CRUD + <code>open</code>/<code>close</code> + 3-step file upload flow + drafts</td></tr>
<tr><td><b>payment</b></td><td>3</td><td><code>form</code>, <code>tokens-search</code>, <code>charge</code></td></tr>
<tr><td><b>partner</b></td><td>4</td><td><code>users</code>, <code>connect</code>, <code>get</code>, <code>disconnect</code></td></tr>
<tr><td><b>tools</b></td><td>4</td><td><code>occupations</code>, <code>countries</code>, <code>cities</code>, <code>currencies</code></td></tr>
</table>

---

## Usage examples

### Create a proforma invoice (חשבון עסקה)

```bash
cat > /tmp/proforma.json <<'JSON'
{
  "description": "ריטיינר חודשי",
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
morning-cli --json document create --file /tmp/proforma.json
```

### Search recent clients

```bash
morning-cli --json client search --data '{"page":1,"pageSize":10}'
```

### Get PDF download link for a document

```bash
morning-cli --json document download <document_id>
```

---

## JSON output for AI agents

Every `--json` command returns a consistent envelope:

```json
{"ok": true, "op": "document.create", "data": {"id": "...", "number": 12345}}
```

Errors include the morning `errorCode` and Hebrew `errorMessage`:

```json
{"ok": false, "op": "document.create", "error": {"code": 1110, "message": "מחיר לא תקין.", "http_status": 400}}
```

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Usage / local error |
| `2` | API error (4xx) |
| `3` | Server error (5xx) / network |

<details>
<summary><b>Common morning API error codes</b></summary>

| Code | Meaning |
|---|---|
| `401` | Token expired (CLI auto-refreshes) |
| `1003` | No active business in the account |
| `1006` | Subscription expired |
| `1007` | Missing permission |
| `1012` | Feature requires a higher plan |
| `1110` | Invalid price in a line item |
| `2002` | Wrong email or password |
| `2102` | Can't add more businesses on this plan |
| `2403` | Document type not supported for this business type |

</details>

---

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `MORNING_API_KEY_ID` | API key ID | — |
| `MORNING_API_KEY_SECRET` | API key secret | — |
| `MORNING_ENV` | `sandbox` or `production` | `sandbox` |
| `MORNING_BASE_URL` | Override base URL | auto |

---

<details>
<summary><b>Tests</b> — 55 tests, including 24 live sandbox E2E</summary>

```bash
pip install -e ".[test]"

# Unit tests — no network
pytest cli_anything/greeninvoice/tests/test_core.py -v

# Full suite with live sandbox
export MORNING_SANDBOX_ID=<your-id>
export MORNING_SANDBOX_SECRET=<your-secret>
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/greeninvoice/tests/ -v
```

**Coverage:**
- 27 unit tests — credentials, token management, session locking, payload parsing
- 4 offline E2E — help, version, error envelopes
- 11 read-only smoke tests — every resource group verified against the live sandbox
- 5 paginated search tests — client, supplier, item, expense, document
- 2 mutation round-trips — item CRUD, supplier create/delete
- 5 workflow tests — auth login, business current, document types, full invoice lifecycle, proforma invoice with Hebrew content
- **3 real bugs caught** during development (late-binding, type 305 gate, Tools host/locale)

</details>

<details>
<summary><b>For AI agents</b> — SKILL.md auto-discovery</summary>

`morning-cli` ships a [SKILL.md](cli_anything/greeninvoice/skills/SKILL.md) file
auto-discovered by the REPL banner and Claude Code / Cursor. It contains:

- Full command reference with examples
- Error code table
- Agent-specific guidance (always use `--json`, sandbox defaults, token refresh)
- Non-interactive `auth init` for CI

If you're an agent reading this, start with the SKILL.md.

</details>

<details>
<summary><b>Methodology</b> — cli-anything 7-phase SOP</summary>

Built following the [cli-anything](https://github.com/HKUDS/CLI-Anything) 7-phase pipeline:

1. **Codebase analysis** — parsed the Apiary spec into a 66-endpoint map
2. **Architecture** — REPL-first, `--json` envelopes, session locking, sandbox-first
3. **Implementation** — PEP 420 namespace package `cli_anything.greeninvoice`
4. **Test planning** — TEST.md written before tests
5. **Test implementation** — unit + live E2E
6. **Test documentation** — results appended to TEST.md
7. **PyPI publishing** — `pip install morning-cli`

Full SOP: [GREENINVOICE.md](GREENINVOICE.md)

</details>

---

## Contributing

PRs welcome! Run the tests before submitting:

```bash
pip install -e ".[test]"
pytest cli_anything/greeninvoice/tests/test_core.py -v
```

See [open issues](https://github.com/Jango-AI-com/morning-cli/issues) for good first contributions.

---

<div align="center">

**[JangoAI](https://jango-ai.com)** — AI automation for Israeli businesses

[Website](https://jango-ai.com) · [GitHub](https://github.com/Jango-AI-com) · [morning API docs](https://www.greeninvoice.co.il/api-docs)

<sub>MIT License · morning-cli is a community project and is not officially affiliated with morning Ltd.</sub>

</div>

<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:2563eb,50:7c3aed,100:06b6d4&height=100&section=footer" alt="" width="100%"/>
</p>
