"""Sync orchestration (Track B — app → Zoho).

Pushes Customers, Vendors, Items, SalesOrders, and PurchaseOrders to Zoho CRM.
Each push is idempotent: an ``Idempotency-Key`` header deduplicates replays
within the TTL; a ``crm_mappings`` row keyed on the local id drives create-vs-
update. The state machine writes a pending ``sync_logs`` row before the Zoho
call so a crash mid-flight is always recoverable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable, Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.zoho.client import ZohoClient
from app.clients.zoho.errors import ZohoAPIError, ZohoRateLimitError, ZohoServerError
from app.core.config import Settings
from app.core.exceptions import ConflictError, UpstreamError, UpstreamUnavailableError
from app.models.crm_mapping import MappingEntityType
from app.models.sync_log import SyncDirection, SyncLog, SyncStatus
from app.repositories.idempotency_repo import IdempotencyRepository
from app.repositories.sync_log_repo import SyncLogRepository
from app.schemas.sync import (
    CustomerSyncRequest,
    ItemSyncRequest,
    LeadSyncRequest,
    PurchaseOrderSyncRequest,
    SalesOrderSyncRequest,
    SyncResponse,
    VendorSyncRequest,
)
from app.services.mapping_service import MappingService

logger = logging.getLogger(__name__)

# App SO status → Zoho Sales_Orders Status picklist value.
_SO_STATUS_MAP = {
    "DRAFT": "Draft",
    "SHIPPED": "Delivered",
}

# App PO status → Zoho Purchase_Orders Status picklist value.
_PO_STATUS_MAP = {
    "DRAFT": "Draft",
    "RECEIVED": "Received",
}

# App LeadSource → Zoho Lead_Source picklist value.
_LEAD_SOURCE_MAP = {
    "PHONE_IN": "Cold Call",
    "WALK_IN": "Walk-In",
    "REFERENCE": "Reference",
    "CAMPAIGN": "Advertisement",
    "FIELD_VISIT": "Field Visit",
    "OTHER": "Other",
}

# App LeadStage → Zoho Lead_Status picklist value.
_LEAD_STATUS_MAP = {
    "NEW": "Not Contacted",
    "QUALIFICATION": "Pre-Qualified",
    "NEGOTIATION": "Negotiation",
    "WON": "Closed Won",
    "LOST": "Closed Lost",
}


class SyncService:
    """Push app records to Zoho CRM — idempotently."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        zoho_client: ZohoClient,
    ) -> None:
        self._session = session
        self._settings = settings
        self._zoho = zoho_client
        self._mappings = MappingService(session)
        self._logs = SyncLogRepository(session)
        self._idempotency = IdempotencyRepository(
            session, ttl_hours=settings.idempotency_ttl_hours
        )

    # --- public sync methods --------------------------------------------------

    async def sync_customer(
        self, req: CustomerSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        payload = _customer_payload(req)
        return await self._push(
            entity_type=MappingEntityType.CUSTOMER,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_account,
            update_fn=self._zoho.update_account,
        )

    async def sync_vendor(
        self, req: VendorSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        payload = _vendor_payload(req)
        return await self._push(
            entity_type=MappingEntityType.VENDOR,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_vendor,
            update_fn=self._zoho.update_vendor,
        )

    async def sync_item(
        self, req: ItemSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        payload = _item_payload(req)
        return await self._push(
            entity_type=MappingEntityType.ITEM,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_product,
            update_fn=self._zoho.update_product,
        )

    async def sync_sales_order(
        self, req: SalesOrderSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        account_zoho_id = await self._mappings.zoho_for_local(
            MappingEntityType.CUSTOMER, str(req.customer_id)
        )
        if account_zoho_id is None:
            raise UpstreamError(
                f"Customer {req.customer_id} has not been synced to Zoho yet — "
                "sync the customer first"
            )
        line_items = await self._resolve_so_lines(req)
        payload = _sales_order_payload(req, account_zoho_id, line_items)
        return await self._push(
            entity_type=MappingEntityType.SALES_ORDER,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_sales_order,
            update_fn=self._zoho.update_sales_order,
        )

    async def sync_lead(
        self, req: LeadSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        item_zoho_id: str | None = None
        if req.item_id is not None:
            item_zoho_id = await self._mappings.zoho_for_local(
                MappingEntityType.ITEM, str(req.item_id)
            )
        payload = _lead_payload(req, item_zoho_id)
        return await self._push(
            entity_type=MappingEntityType.LEAD,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_lead,
            update_fn=self._zoho.update_lead,
        )

    async def sync_purchase_order(
        self, req: PurchaseOrderSyncRequest, idempotency_key: str
    ) -> SyncResponse:
        vendor_zoho_id = await self._mappings.zoho_for_local(
            MappingEntityType.VENDOR, str(req.vendor_id)
        )
        if vendor_zoho_id is None:
            raise UpstreamError(
                f"Vendor {req.vendor_id} has not been synced to Zoho yet — "
                "sync the vendor first"
            )
        line_items = await self._resolve_po_lines(req)
        payload = _purchase_order_payload(req, vendor_zoho_id, line_items)
        return await self._push(
            entity_type=MappingEntityType.PURCHASE_ORDER,
            local_id=str(req.id),
            payload=payload,
            idempotency_key=idempotency_key,
            request_body=req.model_dump(mode="json"),
            create_fn=self._zoho.create_purchase_order,
            update_fn=self._zoho.update_purchase_order,
        )

    # --- shared state machine -------------------------------------------------

    async def _push(
        self,
        *,
        entity_type: MappingEntityType,
        local_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
        request_body: dict[str, Any],
        create_fn: Callable[[dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
        update_fn: Callable[[str, dict[str, Any]], Coroutine[Any, Any, dict[str, Any]]],
    ) -> SyncResponse:
        request_hash = _hash_body(request_body)

        # 1. Idempotency check — replay within TTL returns the cached response.
        cached = await self._idempotency.get(idempotency_key)
        if cached is not None:
            if cached.request_hash != request_hash:
                raise ConflictError("Same idempotency key used with a different request body")
            logger.info(
                "sync_idempotent_replay",
                extra={"entity_type": entity_type.value, "local_id": local_id},
            )
            return SyncResponse.model_validate(cached.response_body)

        # 2. Resolve existing mapping (determines create vs update).
        existing_zoho_id = await self._mappings.zoho_for_local(entity_type, local_id)
        operation: str = "updated" if existing_zoho_id else "created"

        # 3. Write pending log and commit before the Zoho call.
        log = SyncLog(
            direction=SyncDirection.PUSH,
            entity_type=entity_type,
            local_id=local_id,
            zoho_id=existing_zoho_id,
            operation=f"{'update' if existing_zoho_id else 'create'}_{entity_type.value.lower()}",
            status=SyncStatus.PENDING,
            attempt=1,
            idempotency_key=idempotency_key,
            request_payload=payload,
        )
        await self._logs.add(log)
        await self._session.commit()

        # 4. Call Zoho (outside any DB transaction).
        start_ms = int(time.monotonic() * 1000)
        try:
            if existing_zoho_id:
                body = await update_fn(existing_zoho_id, payload)
                zoho_id = existing_zoho_id
            else:
                body = await create_fn(payload)
                zoho_id = _extract_zoho_id(body)
        except ZohoRateLimitError as exc:
            await self._fail_log(log, "RATE_LIMITED", str(exc), start_ms, SyncStatus.RATE_LIMITED)
            raise UpstreamUnavailableError("Zoho rate limit reached") from exc
        except (ZohoServerError, ZohoAPIError) as exc:
            await self._fail_log(log, "UPSTREAM_ERROR", str(exc), start_ms, SyncStatus.FAILED)
            raise UpstreamError(f"Zoho call failed: {exc}") from exc

        # 5. Persist success: update log, record mapping, cache idempotency key.
        latency = int(time.monotonic() * 1000) - start_ms
        log.status = SyncStatus.SUCCESS
        log.zoho_id = zoho_id
        log.latency_ms = latency
        await self._mappings.record_push(entity_type, local_id, zoho_id)
        response = SyncResponse(zoho_id=zoho_id, operation=operation)
        await self._idempotency.save(
            key=idempotency_key,
            request_hash=request_hash,
            response_body=response.model_dump(),
            status_code=200,
        )
        await self._session.commit()

        logger.info(
            "sync_push_success",
            extra={
                "entity_type": entity_type.value,
                "local_id": local_id,
                "zoho_id": zoho_id,
                "operation": operation,
                "latency_ms": latency,
            },
        )
        return response

    async def _fail_log(
        self,
        log: SyncLog,
        error_code: str,
        error_message: str,
        start_ms: int,
        status: SyncStatus,
    ) -> None:
        log.status = status
        log.error_code = error_code
        log.error_message = error_message
        log.latency_ms = int(time.monotonic() * 1000) - start_ms
        await self._session.commit()

    # --- line-item resolution helpers ----------------------------------------

    async def _resolve_so_lines(
        self, req: SalesOrderSyncRequest
    ) -> list[dict[str, Any]]:
        lines = []
        for line in req.items:
            product_zoho_id = await self._mappings.zoho_for_local(
                MappingEntityType.ITEM, str(line.item_id)
            )
            if product_zoho_id is None:
                raise UpstreamError(
                    f"Item {line.item_id} has not been synced to Zoho yet — "
                    "sync all items first"
                )
            qty = float(line.quantity)
            price = float(line.unit_price)
            lines.append({
                "product": {"id": product_zoho_id},
                "quantity": qty,
                "unit_price": price,
                "list_price": price,
                "total": round(qty * price, 2),
                "discount": 0,
            })
        return lines

    async def _resolve_po_lines(
        self, req: PurchaseOrderSyncRequest
    ) -> list[dict[str, Any]]:
        lines = []
        for line in req.items:
            product_zoho_id = await self._mappings.zoho_for_local(
                MappingEntityType.ITEM, str(line.item_id)
            )
            if product_zoho_id is None:
                raise UpstreamError(
                    f"Item {line.item_id} has not been synced to Zoho yet — "
                    "sync all items first"
                )
            qty = float(line.quantity)
            price = float(line.unit_price)
            lines.append({
                "product": {"id": product_zoho_id},
                "quantity": qty,
                "unit_price": price,
                "list_price": price,
                "total": round(qty * price, 2),
                "discount": 0,
            })
        return lines


# --- pure Zoho payload builders (app model → Zoho field names) ---------------

def _customer_payload(req: CustomerSyncRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Account_Name": req.company_name,
        "Industry": "Manufacturing",
        "Inventory_ID": str(req.id),
        "is_privileged": req.is_privileged,
        "competitive_risk_level": req.competitive_risk_level,
        "Customer_Type": req.customer_type,
    }
    if req.contact_person:
        payload["Contact_Person"] = req.contact_person
    if req.email:
        payload["Email"] = req.email
    if req.phone:
        payload["Phone"] = req.phone
    if req.address:
        payload["Billing_Street"] = req.address
    if req.state:
        payload["Billing_State"] = req.state
    if req.city:
        payload["Billing_City"] = req.city
    if req.pincode:
        payload["Billing_Code"] = req.pincode
    if req.district:
        payload["District"] = req.district
    if req.gstin:
        payload["GSTIN"] = req.gstin
    if req.customer_code:
        payload["customer_code"] = req.customer_code
    if req.notes:
        payload["Description"] = req.notes
    return payload


def _vendor_payload(req: VendorSyncRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Vendor_Name": req.vendor_name,
        "Category": "Manufacturing — Raw Material Supplier",
        "Inventory_ID": str(req.id),
    }
    if req.contact_person:
        payload["Contact_Person"] = req.contact_person
    if req.vendor_code:
        payload["Vendor_Code"] = req.vendor_code
    if req.email:
        payload["Email"] = req.email
    if req.phone:
        payload["Phone"] = req.phone
    if req.address:
        payload["Street"] = req.address
    if req.gstin:
        payload["GSTIN"] = req.gstin
    if req.notes:
        payload["Description"] = req.notes
    return payload


def _item_payload(req: ItemSyncRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Product_Name": req.name,
        "Product_Code": req.sku,
        "Product_Category": req.item_type,
        "Unit_Price": float(req.unit_price),
        "Inventory_ID": str(req.id),
    }
    if req.reorder_threshold is not None:
        payload["Reorder_Threshold"] = int(req.reorder_threshold)
    # Usage_Unit is a Zoho Inventory/Books field — not present in Zoho CRM Products.
    # Create a custom text field "Usage_Unit" in the Products module if you need
    # unit_of_measure visible in Zoho, then add: payload["Usage_Unit"] = req.unit_of_measure
    return payload


def _lead_payload(req: LeadSyncRequest, item_zoho_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Last_Name": req.contact_name,
        "Lead_Source": _LEAD_SOURCE_MAP.get(req.source, "Other"),
        "Lead_Status": _LEAD_STATUS_MAP.get(req.stage, "Not Contacted"),
        "Inventory_ID": str(req.id),
    }
    if req.phone:
        payload["Phone"] = req.phone
    if req.email:
        payload["Email"] = req.email
    if req.state:
        payload["State"] = req.state
    if req.city:
        payload["City"] = req.city
    if req.district:
        payload["District"] = req.district
    if req.pincode:
        payload["Zip_Code"] = req.pincode
    if req.notes:
        payload["Description"] = req.notes
    if req.estimated_budget is not None:
        payload["Estimated_Budget"] = float(req.estimated_budget)
    if req.quantity is not None:
        payload["Quantity"] = req.quantity
    if req.dealer_potential:
        payload["dealer_potential"] = req.dealer_potential
    if req.required_by_date is not None:
        payload["required_by_date"] = req.required_by_date.isoformat()
    if item_zoho_id:
        payload["item_id"] = {"id": item_zoho_id}
    return payload


def _sales_order_payload(
    req: SalesOrderSyncRequest,
    account_zoho_id: str,
    line_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Subject": req.so_number,
        "Account_Name": {"id": account_zoho_id},
        "Status": _SO_STATUS_MAP.get(req.status, "Draft"),
        "Order_Date": req.order_date.isoformat(),
        "Inventory_ID": str(req.id),
    }
    if req.expected_delivery_date is not None:
        payload["Expected_Delivery_Date"] = req.expected_delivery_date.isoformat()
    if req.notes:
        payload["Description"] = req.notes
    if line_items:
        payload["Product_Details"] = line_items
    return payload


def _purchase_order_payload(
    req: PurchaseOrderSyncRequest,
    vendor_zoho_id: str,
    line_items: list[dict[str, Any]],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "Subject": req.po_number,
        "Vendor_Name": {"id": vendor_zoho_id},
        "Status": _PO_STATUS_MAP.get(req.status, "Draft"),
        "PO_Date": req.order_date.isoformat(),
        "Inventory_ID": str(req.id),
    }
    if req.notes:
        payload["Description"] = req.notes
    if line_items:
        payload["Product_Details"] = line_items
    return payload


# --- response helpers --------------------------------------------------------

def _extract_zoho_id(body: dict[str, Any]) -> str:
    """Extract the Zoho record id from a successful POST/PUT response body."""
    data = body.get("data")
    if not isinstance(data, list) or not data:
        raise ZohoAPIError("Unexpected Zoho push response shape")
    first = data[0]
    if str(first.get("code", "")).upper() != "SUCCESS":
        raise ZohoAPIError(f"Zoho rejected the record: {first.get('message', 'unknown error')}")
    details = first.get("details") or {}
    zoho_id = details.get("id")
    if not zoho_id:
        raise ZohoAPIError("Zoho push response missing record id")
    return str(zoho_id)


def _hash_body(body: dict[str, Any]) -> str:
    """SHA-256 of the canonicalised (sorted-keys) JSON body."""
    canonical = json.dumps(body, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()
