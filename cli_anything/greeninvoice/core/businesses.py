"""/businesses/* — business profile, numbering, files, types.

Maps 10 endpoints from the Businesses resource group.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def list_all(b: GreenInvoiceBackend) -> Any:
    """GET /businesses — list all businesses owned by the authenticated user."""
    return b.get("/businesses")


def get_current(b: GreenInvoiceBackend) -> Any:
    """GET /businesses/me — current (default) business."""
    return b.get("/businesses/me")


def get_by_id(b: GreenInvoiceBackend, business_id: str) -> Any:
    """GET /businesses/{id}."""
    return b.get(f"/businesses/{business_id}")


def update(b: GreenInvoiceBackend, payload: dict) -> Any:
    """PUT /businesses — update the current business profile."""
    return b.put("/businesses", json=payload)


def upload_file(b: GreenInvoiceBackend, kind: str, file_path: Path) -> Any:
    """POST /businesses/file — upload business file (logo, signature, stamp).

    ``kind`` is a Green Invoice file type code (e.g. logo=0, signature=1, stamp=2).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, "application/octet-stream")}
        return b.post("/businesses/file", files=files, json={"type": kind})


def delete_file(b: GreenInvoiceBackend, kind: str) -> Any:
    """DELETE /businesses/file?type={kind}."""
    return b.delete("/businesses/file", params={"type": kind})


def get_numbering(b: GreenInvoiceBackend) -> Any:
    """GET /businesses/numbering — current document numbering."""
    return b.get("/businesses/numbering")


def update_numbering(b: GreenInvoiceBackend, payload: dict) -> Any:
    """PUT /businesses/numbering — set initial document numbering."""
    return b.put("/businesses/numbering", json=payload)


def get_footer(b: GreenInvoiceBackend) -> Any:
    """GET /businesses/footer."""
    return b.get("/businesses/footer")


def get_types(b: GreenInvoiceBackend, lang: str = "he") -> Any:
    """GET /businesses/types?lang=he|en."""
    return b.get("/businesses/types", params={"lang": lang})
