"""Lead-Intel MCP — listing lookup, price history, market alerts.

When ``LEAD_INTEL_API_URL`` is configured, calls are forwarded to that service.
Otherwise returns a deterministic mock so the UI and agents keep working in dev.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _configured() -> bool:
    return bool(settings.lead_intel_api_url)


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    if not _configured():
        return {}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"{settings.lead_intel_api_url.rstrip('/')}{path}",
                params=params,
                headers={"Authorization": f"Bearer {settings.lead_intel_api_key}"} if settings.lead_intel_api_key else {},
            )
            r.raise_for_status()
            return r.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("lead-intel request failed: %s", exc)
        return {}


async def lookup_listing(address: str) -> dict[str, Any]:
    remote = await _get("/listing", {"address": address})
    if remote:
        return remote
    # Mock fallback
    return {
        "address": address,
        "status": "active",
        "list_price": 465000,
        "beds": 3,
        "baths": 2,
        "sqft": 1820,
        "year_built": 2012,
        "days_on_market": 14,
        "source": "mock",
    }


async def price_history(address: str) -> dict[str, Any]:
    remote = await _get("/price-history", {"address": address})
    if remote:
        return remote
    return {
        "address": address,
        "history": [
            {"date": "2024-06-01", "price": 440000, "event": "listed"},
            {"date": "2024-09-15", "price": 455000, "event": "price_increase"},
            {"date": "2025-01-10", "price": 465000, "event": "relisted"},
        ],
        "source": "mock",
    }


async def market_alert(zip_code: str) -> dict[str, Any]:
    remote = await _get("/market-alert", {"zip": zip_code})
    if remote:
        return remote
    return {
        "zip_code": zip_code,
        "median_list_price": 438000,
        "median_days_on_market": 22,
        "inventory_months": 2.4,
        "trend": "seller_market",
        "source": "mock",
    }


LEAD_INTEL_TOOLS = [
    {"name": "lookup_listing", "description": "Look up a property listing by address", "input_schema": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}},
    {"name": "price_history", "description": "Get price history for a property", "input_schema": {"type": "object", "properties": {"address": {"type": "string"}}, "required": ["address"]}},
    {"name": "market_alert", "description": "Get market conditions for a zip code", "input_schema": {"type": "object", "properties": {"zip_code": {"type": "string"}}, "required": ["zip_code"]}},
]


async def handle_lead_intel_tool_call(name: str, arguments: dict) -> dict:
    if name == "lookup_listing":
        return await lookup_listing(arguments["address"])
    if name == "price_history":
        return await price_history(arguments["address"])
    if name == "market_alert":
        return await market_alert(arguments["zip_code"])
    raise ValueError(f"Unknown lead-intel tool: {name}")
