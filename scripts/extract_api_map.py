#!/usr/bin/env python3
"""Extract a compact API map from the Apiary API Elements JSON.

Input:  spec/greeninvoice.api-elements.json (1.4 MB, full parsed blueprint)
Output: spec/api-map.json (compact map of all endpoints)
        spec/api-description.html (the top-level description HTML)

The compact map has this shape:

{
  "name": "...",
  "base_url": "...",
  "groups": [
    {
      "name": "Documents",
      "description": "...",
      "resources": [
        {
          "name": "Create document",
          "uri_template": "/documents",
          "actions": [
            {
              "method": "POST",
              "name": "Create document",
              "description": "...",
              "parameters": [{"name": "...", "type": "...", "required": true}],
              "request_schema_ref": "DocumentCreate",
              "response_schema_ref": "Document",
              "examples": {"request": "...", "response": "..."}
            }
          ]
        }
      ]
    }
  ],
  "data_structures": ["Currency", "Document", ...]
}
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

SPEC_PATH = pathlib.Path("spec/greeninvoice.api-elements.json")
MAP_PATH = pathlib.Path("spec/api-map.json")
DESC_PATH = pathlib.Path("spec/api-description.html")

# Apiary public description endpoint for morning by Green Invoice.
# Returns an API Elements JSON dump of the full parsed blueprint.
APIARY_SPEC_URL = (
    "https://jsapi.apiary.io/apis/greeninvoice/api-description-document"
)
APIARY_BLUEPRINT_URL = "https://jsapi.apiary.io/apis/greeninvoice/blueprint"


def download_spec_if_missing() -> None:
    """Fetch the raw Apiary dump if it's not already on disk.

    The raw dump is gitignored (third-party content) — this helper makes
    ``extract_api_map.py`` a one-command reproducible pipeline.
    """
    if SPEC_PATH.exists() and SPEC_PATH.stat().st_size > 0:
        return
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    for url in (APIARY_SPEC_URL, APIARY_BLUEPRINT_URL):
        try:
            print(f"Fetching {url} ...")
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
                if data and len(data) > 1000:
                    SPEC_PATH.write_bytes(data)
                    print(f"Wrote {SPEC_PATH} ({len(data):,} bytes)")
                    return
        except Exception as exc:  # noqa: BLE001
            print(f"  failed: {exc}", file=sys.stderr)
    print(
        f"ERROR: could not download the Apiary spec from any known URL.\n"
        f"Try manually: curl -o {SPEC_PATH} {APIARY_SPEC_URL}",
        file=sys.stderr,
    )
    sys.exit(1)


def text_or_none(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    return None


def shorten(text: str | None, limit: int = 500) -> str | None:
    if not text:
        return None
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def extract_parameters(params):
    out = []
    for p in params or []:
        out.append(
            {
                "name": p.get("name"),
                "type": p.get("type"),
                "required": p.get("required", False),
                "description": shorten(text_or_none(p.get("description")), 200),
                "default": p.get("default"),
                "example": p.get("example"),
                "values": p.get("values") or None,
            }
        )
    return out


def extract_schema_ref(examples):
    """Try to pull a type name from example request/response if present."""
    for ex in examples or []:
        for rr in ex.get("responses", []) + ex.get("requests", []):
            name = rr.get("name")
            if name:
                return name
    return None


def extract_first_body(examples, kind):
    """Return first request/response body text (kind='requests'|'responses')."""
    for ex in examples or []:
        for rr in ex.get(kind, []):
            body = rr.get("body")
            if body:
                return shorten(body, 2000)
    return None


def main():
    download_spec_if_missing()
    raw = json.loads(SPEC_PATH.read_text())

    # Save the top-level description HTML separately (it has auth + overview text).
    desc_html = raw.get("description", "")
    DESC_PATH.write_text(desc_html)

    out = {
        "name": raw.get("name"),
        "subdomain": raw.get("subdomain"),
        "last_updated": raw.get("lastUpdated"),
        "base_url": (raw.get("urls") or {}).get("production"),
        "mock_url": (raw.get("urls") or {}).get("mock"),
        "data_structures": [],
        "groups": [],
    }

    # Extract data structure names
    for ds in raw.get("dataStructures", []):
        for elem in ds.get("content", []):
            meta = elem.get("meta", {})
            id_node = meta.get("id") if isinstance(meta, dict) else None
            if isinstance(id_node, dict):
                name = id_node.get("content")
                if name:
                    out["data_structures"].append(name)

    # Walk resource groups → resources → actions
    for g in raw.get("resourceGroups", []):
        grp = {
            "name": g.get("name"),
            "description": shorten(text_or_none(g.get("description")), 1000),
            "resources": [],
        }
        for r in g.get("resources", []):
            res = {
                "name": r.get("name"),
                "uri_template": r.get("uriTemplate"),
                "description": shorten(text_or_none(r.get("description")), 500),
                "parameters": extract_parameters(r.get("parameters")),
                "actions": [],
            }
            for a in r.get("actions", []):
                act = {
                    "method": a.get("method"),
                    "name": a.get("name"),
                    "description": shorten(text_or_none(a.get("description")), 1000),
                    "parameters": extract_parameters(a.get("parameters")),
                    "schema_ref": extract_schema_ref(a.get("examples")),
                    "request_body_sample": extract_first_body(a.get("examples"), "requests"),
                    "response_body_sample": extract_first_body(a.get("examples"), "responses"),
                }
                res["actions"].append(act)
            grp["resources"].append(res)
        out["groups"].append(grp)

    MAP_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    # Print a human summary
    total_actions = sum(
        len(r["actions"]) for g in out["groups"] for r in g["resources"]
    )
    print(f"API: {out['name']}")
    print(f"Base URL: {out['base_url']}")
    print(f"Last updated: {out['last_updated']}")
    print(f"Data structures: {len(out['data_structures'])}")
    print(f"Resource groups: {len(out['groups'])}")
    print(f"Total endpoints: {total_actions}")
    print()
    for g in out["groups"]:
        n_actions = sum(len(r["actions"]) for r in g["resources"])
        print(f"  {g['name']:30s}  resources={len(g['resources']):3d}  endpoints={n_actions:3d}")
    print()
    print(f"Wrote: {MAP_PATH} ({MAP_PATH.stat().st_size:,} bytes)")
    print(f"Wrote: {DESC_PATH} ({DESC_PATH.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
