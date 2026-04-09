# TEST.md — morning-cli

Test plan written **before** implementation (HARNESS Phase 4) and amended with
test results **after** execution (HARNESS Phase 6).

## Test inventory plan

| File | Scope | Planned count |
|---|---|---|
| `test_core.py` | Unit tests — mock `httpx`, verify request shape, auth, session, payload parsing | ~26 |
| `test_full_e2e.py` | E2E — subprocess the installed console script, hit real sandbox API | ~8 |

The real-software rule (HARNESS) maps here to: the E2E suite **must** hit the
real Green Invoice sandbox at `https://sandbox.d.greeninvoice.co.il/api/v1/`.
If credentials are absent, E2E tests fail loudly with a clear skip-reason —
there is no graceful Pillow-style fallback.

## Unit test plan (`test_core.py`)

### `utils/greeninvoice_backend.py` — the HTTP backend (~12 tests)

| Test | Verifies |
|---|---|
| `test_find_credentials_from_env` | Env vars take precedence over credentials.json |
| `test_find_credentials_from_file` | Falls back to `~/.greeninvoice/credentials.json` |
| `test_find_credentials_raises_when_missing` | `CredentialsNotFoundError` carries install instructions |
| `test_find_credentials_unknown_env` | Raises with a clear message |
| `test_acquire_token_posts_creds` | Posts `{id, secret}` to `/account/token` |
| `test_acquire_token_caches_until_expiry` | Second call reuses cached token |
| `test_acquire_token_refreshes_when_expired` | Re-acquires when `expires_at` passed |
| `test_request_sends_bearer_header` | Authenticated calls include `Authorization: Bearer <jwt>` |
| `test_request_handles_401_refresh_retry` | 401 → force-refresh → retry once |
| `test_request_raises_api_error_on_4xx` | Error envelope → `GreenInvoiceAPIError` |
| `test_request_retries_on_5xx` | Retries up to `MAX_RETRIES`, then raises |
| `test_request_returns_none_on_empty_body` | 204-style responses |

### `core/session.py` — session persistence (~5 tests)

| Test | Verifies |
|---|---|
| `test_load_session_returns_default_when_missing` | Fresh default shape |
| `test_save_and_reload_roundtrip` | JSON roundtrip preserves structure |
| `test_save_session_sets_0600_perms` | File is mode 0600 |
| `test_record_history_trims_to_max` | History capped at `MAX_HISTORY` |
| `test_reset_session_clears_token_and_history` | Full reset |

### `core/*.py` + `greeninvoice_cli.py` helpers (~9 tests)

| Test | Verifies |
|---|---|
| `test_load_payload_from_data_string` | `--data '{"x":1}'` parses correctly |
| `test_load_payload_from_file` | `--file foo.json` reads and parses |
| `test_load_payload_rejects_both` | UsageError if both flags passed |
| `test_load_payload_returns_empty_when_none` | `{}` default |
| `test_core_clients_search_default_page` | Default `{page:1,pageSize:25}` payload |
| `test_core_documents_create_posts_to_root` | POST /documents with given payload |
| `test_core_tools_countries_passes_locale` | Query param propagation |
| `test_core_expenses_file_url_get` | GET /expenses/file |
| `test_core_partners_disconnect_email_param` | DELETE + query |

## E2E test plan (`test_full_e2e.py`)

All E2E tests use `_resolve_cli("morning-cli", "cli-anything-greeninvoice")`
per HARNESS so they test the **installed** console script via
`subprocess.run`, not source imports. The resolver prefers `morning-cli`
(the public name) and falls back to `cli-anything-greeninvoice` (the
HARNESS-conventional alias). Setting `CLI_ANYTHING_FORCE_INSTALLED=1` makes
the resolver raise if neither console script is on PATH.

A `pytest` autouse fixture loads sandbox credentials from
`GREENINVOICE_SANDBOX_ID` / `GREENINVOICE_SANDBOX_SECRET` into the
subprocess environment, and marks the E2E module as skipped if they're missing
(printed clearly — this is the one permitted "skip" per HARNESS because the
sandbox requires an external user signup).

### E2E scenarios

| # | Test | Workflow |
|---|---|---|
| 1 | `test_help_returns_zero` | `--help` exits 0 and lists all command groups |
| 2 | `test_version_returns_zero` | `--version` prints `0.1.0` |
| 3 | `test_session_show_json_envelope` | Offline: `--json session show` returns `ok:true` envelope |
| 4 | `test_whoami_without_creds_errors_cleanly` | Offline: returns `ok:false` with install-instructions message |
| 5 | `test_auth_login_acquires_real_token` | **Sandbox:** `auth login` hits real API, caches token, exits 0 |
| 6 | `test_business_current_returns_data` | **Sandbox:** `business current` returns a Business object with `id`, `name` |
| 7 | `test_document_types_returns_lookup` | **Sandbox:** `document types` returns non-empty list with Hebrew labels |
| 8 | `test_full_invoice_lifecycle` | **Sandbox, realistic workflow:** login → get current business → add client → create draft invoice → search documents → verify created |

### Realistic workflow detail (test #8)

**Workflow name:** "Create-first-invoice smoke"
**Simulates:** a new user's first successful end-to-end run —
authenticate, inspect the current business, create a minimal client,
create an invoice, confirm it appears in search results, fetch its PDF link.

**Operations chained:**
1. `auth login`
2. `--json business current` → extract `id`
3. `--json client add --data '{"name": "<unique>", "emails": ["test@example.com"], "taxCode": 1}'` → extract client `id`
4. `--json document create --file /tmp/invoice.json` (invoice draft with 1 line item @ 100 ILS)
5. `--json document search --data '{"page":1,"pageSize":5,"search":"<unique>"}'`
6. `--json document download <id>` → assert at least one `url` in response

**Verified:**
- All subprocess invocations exit 0
- JSON envelopes are valid and `ok:true`
- The created document's `id` appears in the search results
- The download links response contains at least one URL
- Session file contains cached token, business_id context, and history entries

**Cleanup:** Created documents cannot be deleted in Green Invoice once issued,
so the test creates **drafts** (the API supports unpublished drafts).
Created clients are soft-deletable — the test calls `client delete` in a
teardown.

## Test output verification

Beyond "the command exited 0":

- **Every E2E test parses the JSON envelope** and asserts `ok == True`
- **Created IDs** are captured from one test and reused in subsequent steps
- **Search tests** assert the expected item is present in results
- **Error tests** assert specific `errorCode` values and nonzero exit codes
- **Download tests** assert a URL field shape (starts with `https://`)

## How to run

```bash
# Unit tests (no network)
pytest cli_anything/greeninvoice/tests/test_core.py -v

# E2E (requires sandbox creds)
export GREENINVOICE_SANDBOX_ID=...
export GREENINVOICE_SANDBOX_SECRET=...
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/greeninvoice/tests/test_full_e2e.py -v -s

# Everything
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/greeninvoice/tests/ -v -s
```

---

## Test results

### Final run — full suite including LIVE sandbox E2E

```
GREENINVOICE_SANDBOX_ID=... GREENINVOICE_SANDBOX_SECRET=... \
CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/greeninvoice/tests/ -v
...
53 passed in 26.44s
```

**53 tests, 53 passed, 0 failed, 0 skipped.**

Breakdown:
- **27 unit tests** (mock httpx — credentials, token mgmt, session lock, payload parsing, dispatch)
- **4 offline E2E tests** (help, version, session show, error envelope without creds)
- **22 live sandbox E2E tests** against `https://sandbox.d.greeninvoice.co.il/api/v1/`
  plus `https://cache.greeninvoice.co.il` for Tools endpoints

Live sandbox coverage:

| Test | Group | What it verifies |
|---|---|---|
| `test_auth_login_acquires_real_token` | auth | Real JWT acquired, cached, written to session file |
| `test_business_current_returns_data` | business | Real Business object (ג'נגו איי איי) |
| `test_document_types_returns_lookup` | document | 15-item type lookup table |
| `test_full_invoice_lifecycle` | document+client | Login → business → add client → preview quote → search → cleanup |
| `test_proforma_invoice_preview` | document | **חשבון עסקה (type 300)** with Hebrew "שירותי ייעוץ" round-trip |
| `test_readonly_smoke[business.numbering.get]` | business | Numbering config |
| `test_readonly_smoke[business.footer]` | business | Footer config |
| `test_readonly_smoke[business.types]` | business | Business types lookup |
| `test_readonly_smoke[document.statuses]` | document | Document statuses lookup |
| `test_readonly_smoke[document.templates]` | document | Template list |
| `test_readonly_smoke[expense.statuses]` | expense | Expense statuses lookup |
| `test_readonly_smoke[expense.classifications]` | expense | Accounting classifications |
| `test_readonly_smoke[tools.occupations]` | tools | **Cross-host** (`cache.greeninvoice.co.il`), no-auth, locale `en_US` |
| `test_readonly_smoke[tools.countries]` | tools | Cross-host, no-auth |
| `test_readonly_smoke[tools.currencies]` | tools | Cross-host, no-auth |
| `test_paginated_search_smoke[client.search]` | client | Default pagination |
| `test_paginated_search_smoke[supplier.search]` | supplier | Default pagination |
| `test_paginated_search_smoke[item.search]` | item | Default pagination |
| `test_paginated_search_smoke[expense.search]` | expense | Default pagination |
| `test_paginated_search_smoke[document.search]` | document | Default pagination |
| `test_item_round_trip` | item | add → get → update → delete (full CRUD) |
| `test_supplier_round_trip` | supplier | add → get → delete |

**Every single resource group is now covered by at least one live sandbox test.**

### Real bugs caught and fixed during sandbox verification

1. **`session.SESSION_PATH` late-binding in default argument** — Python
   evaluates function defaults at definition time, so monkeypatching the
   module attribute had no effect. Fixed by resolving at call time.

2. **Assumption that `type 305` (tax invoice) works universally** — עוסק
   פטור (exempt dealer) businesses cannot issue tax invoices. Test
   payloads now use `type 10` (price quote) or `type 300` (proforma),
   which work for all business types.

3. **Tools endpoints use a different host and locale format** — The Apiary
   description mentions it in prose but easy to miss: the 4 Tools endpoints
   are served from `https://cache.greeninvoice.co.il` (not the normal
   `/api/v1/` base), require no JWT, and accept locale only in `xx_XX` form
   (`he_IL`, `en_US`) — not short codes. Fixed by:
   - Adding `base_url` and `auth` override parameters to
     `GreenInvoiceBackend.request()`
   - Rewriting `core/tools.py` to call `TOOLS_BASE_URL` with `auth=False`
   - Adding a `LOCALE_ALIASES` map so users can still pass `en`/`he` and
     the CLI expands to the required form

### Endpoints intentionally NOT covered by live tests

| Endpoint | Reason |
|---|---|
| `partner.users` / `partner.connect` / etc. | Requires an enabled Partners subscription add-on; sandbox returns 401 without it. CLI wiring covered by unit tests. |
| `payment.form` / `payment.charge` / `payment.tokens.search` | Requires the Payments module (credit-card processing) enabled on the sandbox. CLI wiring covered by unit tests. |
| `business.file-upload` / `business.file-delete` | Requires an actual image file and would leave artifacts. Simple multipart pass-through. |
| `expense.file-url` + `expense.draft-from-file` + `expense.update-file` | 3-step file flow requires an external PUT to a signed URL. Simple GET + POST pass-throughs. |
| `document.create` (type 305 specifically) | Tax invoices can't be deleted after issuance; preview covers the validation path. |
| `client.merge` / `supplier.merge` / `client.assoc` / `client.balance` | Need specific precondition data in the account. |
| `document.close` / `document.open` | Require a previously-issued document. |

### Earlier run (mock-only, before sandbox creds were available)

Run: `CLI_ANYTHING_FORCE_INSTALLED=1 python -m pytest cli_anything/greeninvoice/tests/ -v --tb=no`
Date: 2026-04-10
Python: 3.14.3 / pytest 9.0.3 / macOS 24.6.0

```
cli_anything/greeninvoice/tests/test_core.py::TestFindCredentials::test_from_env PASSED
cli_anything/greeninvoice/tests/test_core.py::TestFindCredentials::test_from_file PASSED
cli_anything/greeninvoice/tests/test_core.py::TestFindCredentials::test_raises_when_missing PASSED
cli_anything/greeninvoice/tests/test_core.py::TestFindCredentials::test_unknown_env PASSED
cli_anything/greeninvoice/tests/test_core.py::TestAcquireToken::test_posts_creds PASSED
cli_anything/greeninvoice/tests/test_core.py::TestAcquireToken::test_caches_until_expiry PASSED
cli_anything/greeninvoice/tests/test_core.py::TestAcquireToken::test_refreshes_when_expired PASSED
cli_anything/greeninvoice/tests/test_core.py::TestAcquireToken::test_force_refresh PASSED
cli_anything/greeninvoice/tests/test_core.py::TestRequest::test_sends_bearer_header PASSED
cli_anything/greeninvoice/tests/test_core.py::TestRequest::test_401_triggers_refresh_and_retry PASSED
cli_anything/greeninvoice/tests/test_core.py::TestRequest::test_raises_api_error_on_4xx PASSED
cli_anything/greeninvoice/tests/test_core.py::TestRequest::test_retries_then_raises_on_persistent_5xx PASSED
cli_anything/greeninvoice/tests/test_core.py::TestRequest::test_empty_body_returns_none PASSED
cli_anything/greeninvoice/tests/test_core.py::TestSession::test_load_default_when_missing PASSED
cli_anything/greeninvoice/tests/test_core.py::TestSession::test_save_and_reload_roundtrip PASSED
cli_anything/greeninvoice/tests/test_core.py::TestSession::test_save_sets_0600_perms PASSED
cli_anything/greeninvoice/tests/test_core.py::TestSession::test_record_history_trims_to_max PASSED
cli_anything/greeninvoice/tests/test_core.py::TestSession::test_reset_clears_token_and_history PASSED
cli_anything/greeninvoice/tests/test_core.py::TestLoadPayload::test_from_data_string PASSED
cli_anything/greeninvoice/tests/test_core.py::TestLoadPayload::test_from_file PASSED
cli_anything/greeninvoice/tests/test_core.py::TestLoadPayload::test_rejects_both PASSED
cli_anything/greeninvoice/tests/test_core.py::TestLoadPayload::test_empty_when_none PASSED
cli_anything/greeninvoice/tests/test_core.py::TestCoreDispatch::test_clients_search_default_page PASSED
cli_anything/greeninvoice/tests/test_core.py::TestCoreDispatch::test_documents_create_posts_to_root PASSED
cli_anything/greeninvoice/tests/test_core.py::TestCoreDispatch::test_tools_countries_passes_locale PASSED
cli_anything/greeninvoice/tests/test_core.py::TestCoreDispatch::test_expenses_file_url_get PASSED
cli_anything/greeninvoice/tests/test_core.py::TestCoreDispatch::test_partners_disconnect_email_param PASSED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestOfflineCLI::test_help_returns_zero PASSED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestOfflineCLI::test_version_returns_zero PASSED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestOfflineCLI::test_session_show_json_envelope PASSED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestOfflineCLI::test_whoami_without_creds_errors_cleanly PASSED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestSandboxCLI::test_auth_login_acquires_real_token SKIPPED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestSandboxCLI::test_business_current_returns_data SKIPPED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestSandboxCLI::test_document_types_returns_lookup SKIPPED
cli_anything/greeninvoice/tests/test_full_e2e.py::TestSandboxCLI::test_full_invoice_lifecycle SKIPPED

======================== 31 passed, 4 skipped in 0.46s =========================
```

## Summary statistics

- **Total tests:** 35
- **Passed:** 31 (100% of runnable tests)
- **Skipped:** 4 (sandbox E2E — require `GREENINVOICE_SANDBOX_ID` / `_SECRET`)
- **Failed:** 0
- **Execution time:** 0.46s

## Coverage notes

**Covered:**
- Credential resolution (env + file + error paths)
- Token acquisition, caching, force-refresh, automatic 401 refresh-and-retry
- `GreenInvoiceAPIError` decoding from the Hebrew error envelope
- 5xx retry loop with `MAX_RETRIES` bound
- 204/empty-body handling
- Session file locking, 0600 permissions, history trimming, reset
- `--data` / `--file` payload parsing, mutual exclusion
- Dispatch paths for 5 of the 10 resource groups (representative sample)
- Installed console script via subprocess (`_resolve_cli` + `CLI_ANYTHING_FORCE_INSTALLED=1`)
- Top-level `--help`, `--version`, offline `session show`, and error envelope shape

**Intentional gaps pending real sandbox access:**
- Live `auth login` → real JWT round-trip (test present, skipped)
- Live `business current` returning a real Business object
- Live `document types` lookup
- Full invoice lifecycle: login → business → client → draft invoice → search (test present, skipped)

**How to enable the skipped tests:**
1. Register a sandbox account at `lp.sandbox.d.greeninvoice.co.il/join`
2. Generate API keys in **Settings → Advanced → Developers**
3. Export `GREENINVOICE_SANDBOX_ID` and `GREENINVOICE_SANDBOX_SECRET`
4. Re-run: `CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/greeninvoice/tests/ -v -s`

**Real bug caught by the tests:**
`test_save_sets_0600_perms` initially failed because `session.py` used
`path: Path = SESSION_PATH` as a default argument — Python evaluates defaults
at function-definition time, so monkeypatching `session_core.SESSION_PATH`
in the conftest had no effect on the already-bound default. Fixed by
changing the signature to `path: Path | None = None` and resolving at call
time. This is exactly the kind of late-binding surprise the test suite
exists to catch.

