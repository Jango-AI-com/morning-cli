"""/expenses/* — expense records, drafts, file upload flow.

Maps 13 endpoints from the Expenses resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def add(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /expenses."""
    return b.post("/expenses", json=payload)


def get(b: GreenInvoiceBackend, expense_id: str) -> Any:
    """GET /expenses/{id}."""
    return b.get(f"/expenses/{expense_id}")


def update(b: GreenInvoiceBackend, expense_id: str, payload: dict) -> Any:
    """PUT /expenses/{id}."""
    return b.put(f"/expenses/{expense_id}", json=payload)


def delete(b: GreenInvoiceBackend, expense_id: str) -> Any:
    """DELETE /expenses/{id}."""
    return b.delete(f"/expenses/{expense_id}")


def search(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /expenses/search."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/expenses/search", json=body)


def open_expense(b: GreenInvoiceBackend, expense_id: str, payload: dict | None = None) -> Any:
    """POST /expenses/{id}/open."""
    return b.post(f"/expenses/{expense_id}/open", json=payload or {})


def close(b: GreenInvoiceBackend, expense_id: str, payload: dict | None = None) -> Any:
    """POST /expenses/{id}/close."""
    return b.post(f"/expenses/{expense_id}/close", json=payload or {})


def statuses(b: GreenInvoiceBackend) -> Any:
    """GET /expenses/statuses."""
    return b.get("/expenses/statuses")


def accounting_classifications(b: GreenInvoiceBackend) -> Any:
    """GET /accounting/classifications/map."""
    return b.get("/accounting/classifications/map")


def get_file_upload_url(b: GreenInvoiceBackend) -> Any:
    """GET /expenses/file — Step 1: get a one-time upload URL.

    morning uses a 3-step expense-file flow:
    1. GET /expenses/file → returns a signed upload URL + file token
    2. PUT the raw bytes to the returned URL (outside this API)
    3. POST /expenses/example with the token to create a draft
    """
    return b.get("/expenses/file")


def create_draft_from_file(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /expenses/example — Step 2.A: create draft from an uploaded file."""
    return b.post("/expenses/example", json=payload)


def update_file(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /expenses/example — Step 2.B: update an existing draft's file.

    Same endpoint, different payload shape (includes ``id`` of existing draft).
    """
    return b.post("/expenses/example", json=payload)


def search_drafts(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /expenses/drafts/search."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/expenses/drafts/search", json=body)
