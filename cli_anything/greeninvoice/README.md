# morning-cli (Python package)

Installed sub-package under the `cli_anything.greeninvoice` namespace.

## Install

```bash
pip install morning-cli
# or, from source:
pip install -e .
```

Two console scripts are registered:
- `morning-cli` — primary user-facing command
- `cli-anything-greeninvoice` — alias preserved for cli-anything methodology compat

## Run

```bash
morning-cli                  # REPL (default)
morning-cli auth init        # interactive setup wizard
morning-cli --help           # command reference
morning-cli --json business current
```

## About

Built by [JangoAI](https://jango-ai.com) using the
[cli-anything](https://github.com/HKUDS/CLI-Anything) methodology.

See the top-level [README.md](../../README.md) and
[GREENINVOICE.md](../../GREENINVOICE.md) for full usage, architecture, and
credential setup.
