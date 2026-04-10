# Changelog

All notable changes to `morning-cli` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-04-10

### Added

- **66 API endpoints** across 10 resource groups: businesses, clients, suppliers,
  items, documents, expenses, payments, partners, tools, plus local auth/session
- **Interactive onboarding wizard** (`morning-cli auth init`) — walks first-time users
  through environment selection, API key creation deep-link, credential entry (hidden
  input), live verification against the real API, and 0600-mode credential persistence
- **REPL** as the default mode (`morning-cli` with no args) with ReplSkin-powered
  banner, prompt, history, and styled output
- **`--json` envelopes** on every command for agent consumption: `{ok, op, data}` on
  success, `{ok, op, error: {code, message, http_status}}` on failure
- **Automatic JWT refresh** — on 401 the CLI re-acquires the token and retries once
- **Sandbox-first defaults** — `MORNING_ENV` defaults to `sandbox` so accidents
  don't touch production
- **Locked session file** at `~/.greeninvoice/session.json` (mode 0600) with
  `fcntl.flock` exclusive locking per the cli-anything HARNESS methodology
- **Tools endpoints** served from `cache.greeninvoice.co.il` (separate host, no JWT,
  locale format `xx_XX`) — occupations, countries, cities, currencies
- **Dual console scripts**: `morning-cli` (primary) + `cli-anything-greeninvoice`
  (alias for cli-anything methodology compat)
- **Dual env var prefix**: `MORNING_*` (preferred) + `GREENINVOICE_*` (legacy fallback)
- **Hebrew error messages** preserved end-to-end (`errorCode` + `errorMessage`)
- **55 tests**: 27 unit (mock httpx) + 4 offline E2E + 24 live sandbox E2E, covering
  all 10 resource groups, item CRUD round-trip, supplier create/delete, proforma
  invoice preview with Hebrew content, and the full invoice lifecycle flow
- **SKILL.md** for AI-agent discovery (auto-detected by ReplSkin banner)
- **Documentation**: README (English), README.he.md (Hebrew), GREENINVOICE.md (SOP),
  TEST.md (plan + results), SKILL.md, .env.example, LICENSE (MIT)

### Discovered during development

- morning (Green Invoice) Tools endpoints use a **separate host**
  (`https://cache.greeninvoice.co.il`) and do **not** require JWT — the Apiary spec
  mentions this only in prose, not in the endpoint definitions
- Locale parameters on the Tools host must be in `xx_XX` form (`he_IL`, `en_US`),
  not two-letter codes — passing `en` returns HTTP 400
- `type 305` (tax invoice) cannot be issued by an עוסק פטור (exempt dealer) business
  — the test suite now uses `type 10` (price quote) and `type 300` (proforma) which
  work for all business types

[0.1.0]: https://github.com/Jango-AI-com/morning-cli/releases/tag/v0.1.0
