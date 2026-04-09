"""/partners/* — cross-account connections between morning users.

Maps 4 endpoints from the Partners resource group.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend


def list_users(b: GreenInvoiceBackend) -> Any:
    """GET /partners/users."""
    return b.get("/partners/users")


def request_connection(b: GreenInvoiceBackend, payload: dict) -> Any:
    """POST /partners/users/connection."""
    return b.post("/partners/users/connection", json=payload)


def get_user(b: GreenInvoiceBackend, email: str) -> Any:
    """GET /partners/users?email={email}."""
    return b.get("/partners/users", params={"email": email})


def disconnect(b: GreenInvoiceBackend, email: str) -> Any:
    """DELETE /partners/users/connection?email={email}."""
    return b.delete("/partners/users/connection", params={"email": email})
