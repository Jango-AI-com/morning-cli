"""/suppliers/* — supplier records (expense counterparts).

Maps 6 endpoints from the Suppliers resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def add(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /suppliers."""
    return b.post("/suppliers", json=payload)


def get(b: GreenInvoiceBackend, supplier_id: str) -> Any:
    """GET /suppliers/{id}."""
    return b.get(f"/suppliers/{supplier_id}")


def update(b: GreenInvoiceBackend, supplier_id: str, payload: dict) -> Any:
    """PUT /suppliers/{id}."""
    return b.put(f"/suppliers/{supplier_id}", json=payload)


def delete(b: GreenInvoiceBackend, supplier_id: str) -> Any:
    """DELETE /suppliers/{id}."""
    return b.delete(f"/suppliers/{supplier_id}")


def search(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /suppliers/search."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/suppliers/search", json=body)


def merge(b: GreenInvoiceBackend, supplier_id: str, payload: dict) -> Any:
    """POST /suppliers/{id}/merge."""
    return b.post(f"/suppliers/{supplier_id}/merge", json=payload)
