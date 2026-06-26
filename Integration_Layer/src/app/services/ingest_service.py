"""Ingest orchestration (Track A — Zoho → app).

Pulls Zoho Leads, Activities (Calls/Meetings/Tasks), and Deals; resolves each
record's owner email → app user and its subject lead → local id; and writes the
result into the Backend via :class:`BackendClient` (never ``inventory_db``
directly). One-way, idempotent, and additive — with ``ZOHO_INGEST_ENABLED``
off the run is a no-op so the AI engines stay deterministic.

Idempotency comes from ``crm_mappings`` keyed on the Zoho id: a record already
mapped is updated (leads) or skipped (append-only activities), never
duplicated. An owner that doesn't resolve to an app user, or a record with no
resolvable subject, is **parked** (logged to ``sync_logs``, status PARKED) —
never guessed, never fatal to the run.

Field mapping (the Zoho record key names) is centralised in the pure helpers at
the bottom of this module. The exact key names follow Zoho CRM v8 conventions
and are the one thing to confirm against the live org during the A0/A1 smoke;
anything unresolved is parked rather than guessed.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.backend.client import BackendClient
from app.clients.backend.errors import BackendError
from app.clients.zoho.client import ZohoClient
from app.core.config import Settings
from app.models.crm_mapping import MappingEntityType
from app.models.sync_log import SyncDirection, SyncLog, SyncStatus
from app.repositories.sync_log_repo import SyncLogRepository
from app.schemas.ingest import IngestRunSummary, IngestStatus, SyncLogEntry
from app.services.mapping_service import MappingService

logger = logging.getLogger(__name__)


class IngestService:
    """Pull from Zoho, attribute, and write to the Backend — idempotently."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        zoho_client: ZohoClient,
        backend_client: BackendClient,
    ) -> None:
        self._session = session
        self._settings = settings
        self._zoho = zoho_client
        self._backend = backend_client
        self._mappings = MappingService(session)
        self._logs = SyncLogRepository(session)
        self._counts: dict[str, int] = {}

    async def run(self) -> IngestRunSummary:
        """Run a full ingest cycle. No-op (and no Zoho call) when disabled."""
        if not self._settings.zoho_ingest_enabled:
            logger.info("ingest_run_skipped_disabled")
            return IngestRunSummary(enabled=False)

        self._counts = {
            "leads_created": 0,
            "leads_updated": 0,
            "activities_created": 0,
            "activities_skipped": 0,
            "deals_applied": 0,
            "parked": 0,
            "failed": 0,
        }
        email_to_user = await self._build_user_map()

        await self._ingest_leads(email_to_user)
        await self._ingest_activities(email_to_user)
        await self._ingest_won_deals()

        logger.info("ingest_run_completed", extra=dict(self._counts))
        return IngestRunSummary(enabled=True, **self._counts)

    async def status(self) -> IngestStatus:
        """Return the most recent sync-log rows (newest first)."""
        rows = await self._logs.list_recent(limit=50)
        return IngestStatus(recent=[SyncLogEntry.model_validate(r) for r in rows])

    # --- entity pipelines -----------------------------------------------------

    async def _build_user_map(self) -> dict[str, str]:
        """Return ``{lowercased email: app user id}`` from the Backend."""
        users = await self._backend.list_users()
        return {
            str(u["email"]).strip().lower(): str(u["id"])
            for u in users
            if u.get("email") and u.get("id")
        }

    async def _ingest_leads(self, email_to_user: dict[str, str]) -> None:
        for record in await self._zoho.get_leads():
            zoho_id = _record_id(record)
            if zoho_id is None:
                continue
            owner = _owner_local_id(record, email_to_user)
            if owner is None:
                await self._park(MappingEntityType.LEAD, zoho_id, "lead", "unmatched owner")
                continue
            try:
                await self._upsert_lead(record, zoho_id, owner)
            except BackendError as exc:
                await self._fail(MappingEntityType.LEAD, zoho_id, "lead", exc)

    async def _upsert_lead(self, record: dict[str, Any], zoho_id: str, owner: str) -> None:
        existing = await self._mappings.local_for_zoho(MappingEntityType.LEAD, zoho_id)
        if existing is not None:
            await self._backend.update_lead(existing, _lead_update_payload(record, owner))
            local_id = existing
            self._counts["leads_updated"] += 1
            operation = "update_lead"
        else:
            result = await self._backend.create_lead(_lead_create_payload(record, owner))
            local_id = str(result["id"])
            await self._mappings.record(MappingEntityType.LEAD, zoho_id, local_id)
            self._counts["leads_created"] += 1
            operation = "create_lead"

        # Capture the lead's converted Deal so a later Closed-Won Deal can be
        # attributed back to this lead (DEAL zoho id → local LEAD id).
        deal_id = _converted_deal_id(record)
        if deal_id is not None:
            await self._mappings.record(MappingEntityType.DEAL, deal_id, local_id)

        await self._success(MappingEntityType.LEAD, zoho_id, local_id, operation)

    async def _ingest_activities(self, email_to_user: dict[str, str]) -> None:
        sources = (
            (await self._zoho.get_calls(), _call_to_activity),
            (await self._zoho.get_events(), _event_to_activity),
            (await self._zoho.get_tasks(), _task_to_activity),
        )
        for records, adapter in sources:
            for record in records:
                await self._ingest_one_activity(record, adapter, email_to_user)

    async def _ingest_one_activity(
        self,
        record: dict[str, Any],
        adapter: Any,
        email_to_user: dict[str, str],
    ) -> None:
        zoho_id = _record_id(record)
        if zoho_id is None:
            return
        # Append-only: an already-ingested activity is never re-created.
        if await self._mappings.local_for_zoho(MappingEntityType.ACTIVITY, zoho_id) is not None:
            self._counts["activities_skipped"] += 1
            return

        owner = _owner_local_id(record, email_to_user)
        if owner is None:
            await self._park(MappingEntityType.ACTIVITY, zoho_id, "activity", "unmatched owner")
            return
        lead_zoho_id = _related_lead_zoho_id(record)
        local_lead = (
            await self._mappings.local_for_zoho(MappingEntityType.LEAD, lead_zoho_id)
            if lead_zoho_id is not None
            else None
        )
        if local_lead is None:
            await self._park(MappingEntityType.ACTIVITY, zoho_id, "activity", "no subject lead")
            return

        payload = adapter(record, rep_user_id=owner, lead_id=local_lead)
        if payload is None:
            await self._park(MappingEntityType.ACTIVITY, zoho_id, "activity", "unmappable record")
            return
        try:
            result = await self._backend.create_activity(payload)
        except BackendError as exc:
            await self._fail(MappingEntityType.ACTIVITY, zoho_id, "activity", exc)
            return
        local_id = str(result["id"])
        await self._mappings.record(MappingEntityType.ACTIVITY, zoho_id, local_id)
        self._counts["activities_created"] += 1
        await self._success(MappingEntityType.ACTIVITY, zoho_id, local_id, "create_activity")

    async def _ingest_won_deals(self) -> None:
        for record in await self._zoho.get_deals():
            zoho_id = _record_id(record)
            if zoho_id is None or not _deal_is_won(record):
                continue
            local_lead = await self._mappings.local_for_zoho(MappingEntityType.DEAL, zoho_id)
            won = _deal_won_fields(record)
            if local_lead is None or won is None:
                reason = (
                    "deal not linked to a tracked lead"
                    if local_lead is None
                    else "no amount/date"
                )
                await self._park(MappingEntityType.DEAL, zoho_id, "deal", reason)
                continue
            try:
                await self._backend.update_lead(local_lead, won)
            except BackendError as exc:
                await self._fail(MappingEntityType.DEAL, zoho_id, "deal", exc)
                continue
            self._counts["deals_applied"] += 1
            await self._success(MappingEntityType.DEAL, zoho_id, local_lead, "apply_won_deal")

    # --- outcome logging (each commits so progress survives a later failure) --

    async def _success(
        self, entity_type: MappingEntityType, zoho_id: str, local_id: str, operation: str
    ) -> None:
        await self._write_log(SyncStatus.SUCCESS, entity_type, zoho_id, local_id, operation, None)

    async def _park(
        self, entity_type: MappingEntityType, zoho_id: str, operation: str, reason: str
    ) -> None:
        self._counts["parked"] += 1
        logger.warning(
            "ingest_record_parked",
            extra={"entity_type": entity_type.value, "zoho_id": zoho_id, "reason": reason},
        )
        await self._write_log(
            SyncStatus.PARKED, entity_type, zoho_id, None, operation, reason, error_code="PARKED"
        )

    async def _fail(
        self, entity_type: MappingEntityType, zoho_id: str, operation: str, exc: BackendError
    ) -> None:
        self._counts["failed"] += 1
        logger.error(
            "ingest_record_failed",
            extra={"entity_type": entity_type.value, "zoho_id": zoho_id, "error": exc.message},
        )
        await self._write_log(
            SyncStatus.FAILED, entity_type, zoho_id, None, operation, exc.message,
            error_code="BACKEND_ERROR",
        )

    async def _write_log(
        self,
        status: SyncStatus,
        entity_type: MappingEntityType,
        zoho_id: str,
        local_id: str | None,
        operation: str,
        error_message: str | None,
        *,
        error_code: str | None = None,
    ) -> None:
        await self._logs.add(
            SyncLog(
                direction=SyncDirection.INGEST,
                entity_type=entity_type,
                zoho_id=zoho_id,
                local_id=local_id,
                operation=operation,
                status=status,
                attempt=1,
                error_code=error_code,
                error_message=error_message,
            )
        )
        await self._session.commit()


# --- pure Zoho-record adapters (v8 field names — confirm at live smoke) -------

# Zoho Lead_Source → app LeadSource value (lowercased match; default OTHER).
_SOURCE_MAP = {
    "referral": "REFERENCE",
    "reference": "REFERENCE",
    "phone": "PHONE_IN",
    "cold call": "PHONE_IN",
    "inbound call": "PHONE_IN",
    "walk-in": "WALK_IN",
    "walk in": "WALK_IN",
    "campaign": "CAMPAIGN",
    "advertisement": "CAMPAIGN",
    "online store": "CAMPAIGN",
    "field visit": "FIELD_VISIT",
    "trade show": "FIELD_VISIT",
}

# Zoho Lead_Status → app LeadStage (in-funnel only). WON comes solely from a
# Closed-Won Deal; LOST mapping is deferred (a lost lead keeps its last stage),
# so we never fabricate a lost_at/lost_reason.
_STATUS_MAP = {
    "not contacted": "NEW",
    "attempted to contact": "NEW",
    "contact in future": "NEW",
    "contacted": "QUALIFICATION",
    "pre-qualified": "QUALIFICATION",
    "qualified": "QUALIFICATION",
    "negotiation": "NEGOTIATION",
    "proposal": "NEGOTIATION",
}


def _record_id(record: dict[str, Any]) -> str | None:
    value = record.get("id")
    return str(value) if value else None


def _owner_email(record: dict[str, Any]) -> str | None:
    owner = record.get("Owner")
    if isinstance(owner, dict) and owner.get("email"):
        return str(owner["email"]).strip().lower()
    return None


def _owner_local_id(record: dict[str, Any], email_to_user: dict[str, str]) -> str | None:
    email = _owner_email(record)
    return email_to_user.get(email) if email is not None else None


def _lead_contact_name(record: dict[str, Any]) -> str:
    for key in ("Full_Name", "Last_Name", "Company"):
        value = record.get(key)
        if value:
            return str(value)
    return "Unknown"


def _lead_create_payload(record: dict[str, Any], owner: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "contact_name": _lead_contact_name(record),
        "source": _SOURCE_MAP.get(str(record.get("Lead_Source", "")).strip().lower(), "OTHER"),
        "stage": _STATUS_MAP.get(str(record.get("Lead_Status", "")).strip().lower(), "NEW"),
        "assigned_to_user_id": owner,
    }
    _add_optional_lead_fields(record, payload)
    created = record.get("Created_Time")
    if created:
        payload["source_created_at"] = str(created)
    return payload


def _lead_update_payload(record: dict[str, Any], owner: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": _STATUS_MAP.get(str(record.get("Lead_Status", "")).strip().lower(), "NEW"),
        "assigned_to_user_id": owner,
    }
    _add_optional_lead_fields(record, payload)
    return payload


def _add_optional_lead_fields(record: dict[str, Any], payload: dict[str, Any]) -> None:
    if record.get("Phone"):
        payload["phone"] = str(record["Phone"])
    if record.get("Email"):
        payload["email"] = str(record["Email"])
    if record.get("State"):
        payload["state"] = str(record["State"])
    if record.get("City"):
        payload["city"] = str(record["City"])
    if record.get("Zip_Code"):
        payload["pincode"] = str(record["Zip_Code"])
    if record.get("District"):
        payload["district"] = str(record["District"])
    if record.get("Quantity") is not None:
        qty = _int_or_none(record["Quantity"])
        if qty is not None:
            payload["quantity"] = qty
    if record.get("estimated_budget") is not None:
        with contextlib.suppress(TypeError, ValueError):
            payload["estimated_budget"] = float(record["estimated_budget"])
    if record.get("dealer_potential"):
        payload["dealer_potential"] = str(record["dealer_potential"])
    if record.get("required_by_date"):
        payload["required_by_date"] = str(record["required_by_date"])
    # item_id is a Lookup field — Zoho returns {"id": "...", "name": "..."}.
    item_ref = record.get("item_id")
    if isinstance(item_ref, dict) and item_ref.get("id"):
        payload["item_id"] = str(item_ref["id"])
    # Converted_Account links a converted lead to its app Customer record.
    account_ref = record.get("Converted_Account")
    if isinstance(account_ref, dict) and account_ref.get("id"):
        payload["customer_id"] = str(account_ref["id"])


def _converted_deal_id(record: dict[str, Any]) -> str | None:
    """Return the Zoho Deal id a converted lead points to, if present."""
    deal = record.get("Converted_Deal")
    if isinstance(deal, dict) and deal.get("id"):
        return str(deal["id"])
    if deal:  # some orgs expose it as a bare id
        return str(deal)
    return None


def _related_lead_zoho_id(record: dict[str, Any]) -> str | None:
    """Return the Zoho Lead id an activity is about, if it is lead-related."""
    if record.get("$se_module") != "Leads":
        return None
    for key in ("What_Id", "Who_Id"):
        ref = record.get(key)
        if isinstance(ref, dict) and ref.get("id"):
            return str(ref["id"])
    return None


def _call_to_activity(
    record: dict[str, Any], *, rep_user_id: str, lead_id: str
) -> dict[str, Any] | None:
    occurred = record.get("Call_Start_Time")
    if not occurred:
        return None
    payload: dict[str, Any] = {
        "type": "CALL",
        "rep_user_id": rep_user_id,
        "lead_id": lead_id,
        "occurred_at": str(occurred),
    }
    minutes = _int_or_none(record.get("Call_Duration_in_seconds"))
    if minutes is not None and minutes >= 60:
        payload["duration_minutes"] = minutes // 60
    return payload


def _event_to_activity(
    record: dict[str, Any], *, rep_user_id: str, lead_id: str
) -> dict[str, Any] | None:
    start = record.get("Start_DateTime")
    if not start:
        return None
    # A meeting with a Location is treated as a site VISIT (the heaviest effort
    # weight); a location-less meeting stays MEETING (agreed convention, §9).
    has_location = bool(str(record.get("Location") or "").strip())
    payload: dict[str, Any] = {
        "type": "VISIT" if has_location else "MEETING",
        "rep_user_id": rep_user_id,
        "lead_id": lead_id,
        "occurred_at": str(start),
    }
    duration = _event_duration_minutes(start, record.get("End_DateTime"))
    if duration is not None:
        payload["duration_minutes"] = duration
    return payload


def _task_to_activity(
    record: dict[str, Any], *, rep_user_id: str, lead_id: str
) -> dict[str, Any] | None:
    occurred = record.get("Created_Time") or record.get("Due_Date")
    if not occurred:
        return None
    return {
        "type": "FOLLOW_UP",
        "rep_user_id": rep_user_id,
        "lead_id": lead_id,
        "occurred_at": str(occurred),
    }


def _deal_is_won(record: dict[str, Any]) -> bool:
    return str(record.get("Stage", "")).strip().lower() == "closed won"


def _deal_won_fields(record: dict[str, Any]) -> dict[str, Any] | None:
    """Return ``{stage, won_value, won_at}`` for a won Deal, or ``None``."""
    amount = record.get("Amount")
    won_at = _date_to_datetime_iso(record.get("Closing_Date"))
    if amount is None or won_at is None:
        return None
    try:
        if float(amount) <= 0:
            return None
    except (TypeError, ValueError):
        return None
    return {"stage": "WON", "won_value": str(amount), "won_at": won_at}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event_duration_minutes(start: Any, end: Any) -> int | None:
    if not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start))
        end_dt = datetime.fromisoformat(str(end))
    except ValueError:
        return None
    minutes = int((end_dt - start_dt).total_seconds() // 60)
    return minutes if minutes > 0 else None


def _date_to_datetime_iso(value: Any) -> str | None:
    """Convert a Zoho ``Closing_Date`` (YYYY-MM-DD) to a UTC-midnight ISO string."""
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return None
    return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC).isoformat()
