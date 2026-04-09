"""/payments/* — hosted payment forms and saved-card charging.

Maps 3 endpoints from the Payments resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def payment_form(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /payments/form — create a hosted-page payment form URL."""
    return b.post("/payments/form", json=payload)


def search_tokens(b: GreenInvoiceBackend, payload: dict | None = None) -> Any:
    """POST /payments/tokens/search — saved credit-card tokens."""
    body = payload or {"page": 1, "pageSize": 25}
    return b.post("/payments/tokens/search", json=body)


def charge_token(b: GreenInvoiceBackend, token_id: str, payload: dict) -> Any:
    """POST /payments/tokens/{id}/charge — charge a saved card."""
    return b.post(f"/payments/tokens/{token_id}/charge", json=payload)
