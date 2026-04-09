"""/clients/* — client/customer records.

Maps 8 endpoints from the Clients resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def add(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /clients."""
    return b.post("/clients", json=payload)


def get(b: GreenInvoiceBackend, client_id: str) -> Any:
    """GET /clients/{id}."""
    return b.get(f"/clients/{client_id}")


def update(b: GreenInvoiceBackend, client_id: str, payload: dict) -> Any:
    """PUT /clients/{id}."""
    return b.put(f"/clients/{client_id}", json=payload)


def delete(b: GreenInvoiceBackend, client_id: str) -> Any:
    """DELETE /clients/{id}."""
    return b.delete(f"/clients/{client_id}")


def search(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /clients/search — paginated search.

    Payload accepts keys like ``page``, ``pageSize``, ``sort``, ``search``.
    Defaults to first 25 results.
    """
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/clients/search", json=body)


def assoc_documents(b: GreenInvoiceBackend, client_id: str, payload: dict) -> Any:
    """POST /clients/{id}/assoc — attach existing documents to a client."""
    return b.post(f"/clients/{client_id}/assoc", json=payload)


def merge(b: GreenInvoiceBackend, client_id: str, payload: dict) -> Any:
    """POST /clients/{id}/merge — merge two clients."""
    return b.post(f"/clients/{client_id}/merge", json=payload)


def update_balance(b: GreenInvoiceBackend, client_id: str, payload: dict) -> Any:
    """POST /clients/{id}/balance — set opening balance / income."""
    return b.post(f"/clients/{client_id}/balance", json=payload)
