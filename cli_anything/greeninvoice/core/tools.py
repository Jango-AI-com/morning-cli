"""Tools — lookup/reference data (occupations, countries, cities, currencies).

These 4 endpoints are served from a separate public host,
``https://cache.greeninvoice.co.il``, and do NOT require JWT authentication.
This is documented in the Apiary spec for the Tools resource group. The
backend is called with ``base_url=`` override and ``auth=False``.

The ``locale`` parameter uses underscore form (``he_IL``, ``en_US``), not
two-letter codes — passing ``en`` returns a 400 ValidationException.
"""
from __future__ import annotations

from typing import Any

from cli_anything.greeninvoice.utils.greeninvoice_backend import GreenInvoiceBackend

TOOLS_BASE_URL = "https://cache.greeninvoice.co.il"

LOCALE_ALIASES = {
    "he": "he_IL",
    "en": "en_US",
    "ar": "ar_IL",
    "ru": "ru_RU",
}


def _normalize_locale(locale: str) -> str:
    """Allow callers to pass short codes and expand them to xx_XX form."""
    return LOCALE_ALIASES.get(locale, locale)


def occupations(b: GreenInvoiceBackend, locale: str = "he_IL") -> Any:
    """GET https://cache.greeninvoice.co.il/businesses/v1/occupations?locale=..."""
    return b.get(
        "/businesses/v1/occupations",
        params={"locale": _normalize_locale(locale)},
        base_url=TOOLS_BASE_URL,
        auth=False,
    )


def countries(b: GreenInvoiceBackend, locale: str = "he_IL") -> Any:
    """GET https://cache.greeninvoice.co.il/geo-location/v1/countries?locale=..."""
    return b.get(
        "/geo-location/v1/countries",
        params={"locale": _normalize_locale(locale)},
        base_url=TOOLS_BASE_URL,
        auth=False,
    )


def cities(b: GreenInvoiceBackend, country: str, locale: str = "he_IL") -> Any:
    """GET https://cache.greeninvoice.co.il/geo-location/v1/cities?locale=...&country=..."""
    return b.get(
        "/geo-location/v1/cities",
        params={"locale": _normalize_locale(locale), "country": country},
        base_url=TOOLS_BASE_URL,
        auth=False,
    )


def currencies(b: GreenInvoiceBackend, base: str = "ILS") -> Any:
    """GET https://cache.greeninvoice.co.il/currency-exchange/v1/latest?base=..."""
    return b.get(
        "/currency-exchange/v1/latest",
        params={"base": base},
        base_url=TOOLS_BASE_URL,
        auth=False,
    )
