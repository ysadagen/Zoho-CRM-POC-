"""IntegrationLayerClient — fires sync calls from Backend to Integration Layer.

Methods never raise. Errors are logged so a BackgroundTask failure never
surfaces to the caller or corrupts the Backend response. The caller (Backend)
is always the source of truth; sync failure is recoverable via IL retry tooling.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

_IL_KEY_HEADER = "X-Internal-API-Key"


class IntegrationLayerClient:
    """Push entity records to the Integration Layer sync endpoints."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.integration_layer_base_url.rstrip("/")
        self._api_key = settings.integration_layer_api_key
        self._timeout = float(settings.integration_layer_timeout_seconds)

    # --- public sync methods --------------------------------------------------

    async def sync_customer(
        self,
        *,
        id: uuid.UUID,
        company_name: str,
        contact_person: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
        state: str | None,
        district: str | None,
        city: str | None,
        pincode: str | None,
        gstin: str | None,
        customer_code: str | None,
        customer_type: str,
        is_privileged: bool,
        competitive_risk_level: str,
        notes: str | None,
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "company_name": company_name,
            "contact_person": contact_person,
            "email": email,
            "phone": phone,
            "address": address,
            "state": state,
            "district": district,
            "city": city,
            "pincode": pincode,
            "gstin": gstin,
            "customer_code": customer_code,
            "customer_type": customer_type,
            "is_privileged": is_privileged,
            "competitive_risk_level": competitive_risk_level,
            "notes": notes,
        }
        key = _idempotency_key("customer", id, updated_at)
        await self._post("/api/v1/sync/customers", payload, key)

    async def sync_vendor(
        self,
        *,
        id: uuid.UUID,
        vendor_name: str,
        contact_person: str | None,
        vendor_code: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
        gstin: str | None,
        notes: str | None,
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "vendor_name": vendor_name,
            "contact_person": contact_person,
            "vendor_code": vendor_code,
            "email": email,
            "phone": phone,
            "address": address,
            "gstin": gstin,
            "notes": notes,
        }
        key = _idempotency_key("vendor", id, updated_at)
        await self._post("/api/v1/sync/vendors", payload, key)

    async def sync_item(
        self,
        *,
        id: uuid.UUID,
        name: str,
        sku: str,
        item_type: str,
        unit_of_measure: str,
        unit_price: Decimal,
        reorder_threshold: Decimal | None,
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "name": name,
            "sku": sku,
            "item_type": item_type,
            "unit_of_measure": unit_of_measure,
            "unit_price": str(unit_price),
        }
        if reorder_threshold is not None:
            payload["reorder_threshold"] = str(reorder_threshold)
        await self._post("/api/v1/sync/items", payload, _idempotency_key("item", id, updated_at))

    async def sync_sales_order(
        self,
        *,
        id: uuid.UUID,
        so_number: str,
        customer_id: uuid.UUID,
        order_date: str,
        expected_delivery_date: str | None,
        status: str,
        notes: str | None,
        items: list[dict[str, Any]],
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "so_number": so_number,
            "customer_id": str(customer_id),
            "order_date": order_date,
            "expected_delivery_date": expected_delivery_date,
            "status": status,
            "notes": notes,
            "items": items,
        }
        key = _idempotency_key("sales_order", id, updated_at)
        await self._post("/api/v1/sync/sales-orders", payload, key)

    async def sync_purchase_order(
        self,
        *,
        id: uuid.UUID,
        po_number: str,
        vendor_id: uuid.UUID,
        order_date: str,
        status: str,
        notes: str | None,
        items: list[dict[str, Any]],
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "po_number": po_number,
            "vendor_id": str(vendor_id),
            "order_date": order_date,
            "status": status,
            "notes": notes,
            "items": items,
        }
        key = _idempotency_key("purchase_order", id, updated_at)
        await self._post("/api/v1/sync/purchase-orders", payload, key)

    async def sync_lead(
        self,
        *,
        id: uuid.UUID,
        contact_name: str,
        source: str,
        stage: str,
        phone: str | None,
        email: str | None,
        state: str | None,
        district: str | None,
        city: str | None,
        pincode: str | None,
        notes: str | None,
        estimated_budget: Decimal | None,
        quantity: Decimal | None,
        item_id: uuid.UUID | None,
        dealer_potential: str | None,
        required_by_date: str | None,
        updated_at: datetime,
    ) -> None:
        payload: dict[str, Any] = {
            "id": str(id),
            "contact_name": contact_name,
            "source": source,
            "stage": stage,
            "phone": phone,
            "email": email,
            "state": state,
            "district": district,
            "city": city,
            "pincode": pincode,
            "notes": notes,
            "dealer_potential": dealer_potential,
            "required_by_date": required_by_date,
        }
        if estimated_budget is not None:
            payload["estimated_budget"] = str(estimated_budget)
        if quantity is not None:
            payload["quantity"] = int(quantity)
        if item_id is not None:
            payload["item_id"] = str(item_id)
        key = _idempotency_key("lead", id, updated_at)
        await self._post("/api/v1/sync/leads", payload, key)

    async def trigger_ingest(self) -> dict[str, Any]:
        """Trigger a Zoho ingest cycle on the Integration Layer.

        Returns the IL's response body on success, or a dict describing the
        failure. Never raises — errors are logged and a safe dict is returned
        so the caller can surface them to the UI gracefully.
        """
        url = f"{self._base_url}/api/v1/ingest/run"
        headers = {_IL_KEY_HEADER: self._api_key}
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, headers=headers)
            if resp.status_code not in (200, 201, 202):
                logger.warning(
                    "il_ingest_trigger_non_2xx",
                    extra={"status": resp.status_code, "body": resp.text[:300]},
                )
                return {"ok": False, "status": resp.status_code, "detail": resp.text[:300]}
            logger.info("il_ingest_trigger_ok", extra={"status": resp.status_code})
            body: dict[str, Any] = resp.json() if resp.content else {}
            body["ok"] = True
            return body
        except Exception as exc:
            logger.error("il_ingest_trigger_error", exc_info=exc)
            return {"ok": False, "detail": str(exc)}

    # --- internals -----------------------------------------------------------

    async def _post(self, path: str, payload: dict[str, Any], idempotency_key: str) -> None:
        url = f"{self._base_url}{path}"
        headers = {
            _IL_KEY_HEADER: self._api_key,
            "Idempotency-Key": idempotency_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code not in (200, 201):
                logger.warning(
                    "il_sync_non_2xx",
                    extra={"path": path, "status": resp.status_code, "body": resp.text[:300]},
                )
            else:
                logger.info("il_sync_ok", extra={"path": path, "status": resp.status_code})
        except Exception as exc:
            logger.error("il_sync_error", exc_info=exc, extra={"path": path})


def _idempotency_key(entity_type: str, entity_id: uuid.UUID, updated_at: datetime) -> str:
    """Deterministic key so replays of the same mutation hit the IL cache."""
    raw = f"{entity_type}:{entity_id}:{updated_at.isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()
