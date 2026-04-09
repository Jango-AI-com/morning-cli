"""/documents/* — invoices, receipts, quotes, orders, etc.

Maps 13 endpoints from the Documents resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def create(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /documents — create a real document (invoice/receipt/etc.).

    The ``type`` field selects the document kind (305=invoice, 320=receipt, ...).
    ``lang``, ``currency``, ``vatType``, ``client``, ``income`` are required.
    """
    return b.post("/documents", json=payload)


def preview(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /documents/preview — preview without committing."""
    return b.post("/documents/preview", json=payload)


def get(b: GreenInvoiceBackend, document_id: str) -> Any:
    """GET /documents/{id}."""
    return b.get(f"/documents/{document_id}")


def search(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /documents/search."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/documents/search", json=body)


def search_payments(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /documents/payments/search."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/documents/payments/search", json=body)


def close(b: GreenInvoiceBackend, document_id: str, payload: dict | None = None) -> Any:
    """POST /documents/{id}/close."""
    return b.post(f"/documents/{document_id}/close", json=payload or {})


def open_document(b: GreenInvoiceBackend, document_id: str, payload: dict | None = None) -> Any:
    """POST /documents/{id}/open."""
    return b.post(f"/documents/{document_id}/open", json=payload or {})


def linked(b: GreenInvoiceBackend, document_id: str) -> Any:
    """GET /documents/{id}/linked."""
    return b.get(f"/documents/{document_id}/linked")


def download_links(b: GreenInvoiceBackend, document_id: str) -> Any:
    """GET /documents/{id}/download/links — signed PDF download URLs."""
    return b.get(f"/documents/{document_id}/download/links")


def info(b: GreenInvoiceBackend, type_: int | str) -> Any:
    """GET /documents/info?type=..."""
    return b.get("/documents/info", params={"type": type_})


def templates(b: GreenInvoiceBackend) -> Any:
    """GET /documents/templates."""
    return b.get("/documents/templates")


def types(b: GreenInvoiceBackend, lang: str = "he") -> Any:
    """GET /documents/types?lang=he|en."""
    return b.get("/documents/types", params={"lang": lang})


def statuses(b: GreenInvoiceBackend, lang: str = "he") -> Any:
    """GET /documents/statuses?lang=he|en."""
    return b.get("/documents/statuses", params={"lang": lang})
