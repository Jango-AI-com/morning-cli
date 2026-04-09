"""/items/* — catalog items (products/services).

Maps 5 endpoints from the Items resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def add(b: GreenInvoiceBackend, payload: dict) -> Any:
    return b.post("/items", json=payload)


def get(b: GreenInvoiceBackend, item_id: str) -> Any:
    return b.get(f"/items/{item_id}")


def update(b: GreenInvoiceBackend, item_id: str, payload: dict) -> Any:
    return b.put(f"/items/{item_id}", json=payload)


def delete(b: GreenInvoiceBackend, item_id: str) -> Any:
    return b.delete(f"/items/{item_id}")


def search(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/items/search", json=body)
