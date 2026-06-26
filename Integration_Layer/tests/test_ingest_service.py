"""Tests for the ingest orchestrator (Track A).

Both upstreams are mocked with ``respx`` (Zoho module GETs and the Backend
ingest endpoints); the service runs against a real transactional DB session so
``crm_mappings`` dedupe and ``sync_logs`` parking are exercised end-to-end.
Never hits real Zoho or a real Backend.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.backend.client import BackendClient
from app.clients.zoho.client import ZohoClient
from app.core.config import get_settings
from app.models.crm_mapping import CrmMapping, MappingEntityType
from app.models.sync_log import SyncLog, SyncStatus
from app.services.ingest_service import IngestService

_SETTINGS = get_settings()
_ZOHO = _SETTINGS.zoho_api_base_url.rstrip("/")
_BACKEND_INGEST = f"{_SETTINGS.backend_base_url.rstrip('/')}/api/v1/ingest"

_USER_ID = "22222222-2222-2222-2222-222222222222"
_LEAD_ID = "11111111-1111-1111-1111-111111111111"
_ACTIVITY_ID = "33333333-3333-3333-3333-333333333333"


class _StubTokenProvider:
    async def get_access_token(self) -> str:
        return "access-token"

    async def force_refresh(self) -> str:
        return "access-token"


@pytest.fixture
def ingest_enabled() -> Iterator[None]:
    settings = get_settings()
    original = settings.zoho_ingest_enabled
    settings.zoho_ingest_enabled = True
    try:
        yield
    finally:
        settings.zoho_ingest_enabled = original


@pytest.fixture
def ingest_disabled() -> Iterator[None]:
    settings = get_settings()
    original = settings.zoho_ingest_enabled
    settings.zoho_ingest_enabled = False
    try:
        yield
    finally:
        settings.zoho_ingest_enabled = original


async def _build_service(session: AsyncSession, http_client: httpx.AsyncClient) -> IngestService:
    zoho = ZohoClient(_SETTINGS, http_client, _StubTokenProvider())
    backend = BackendClient(_SETTINGS, http_client)
    return IngestService(
        session=session, settings=_SETTINGS, zoho_client=zoho, backend_client=backend
    )


def _module(mock: respx.MockRouter, name: str, records: list[dict[str, Any]]) -> None:
    """Mock a Zoho module GET to return ``records`` on a single page."""
    mock.get(f"{_ZOHO}/{name}").mock(
        return_value=Response(200, json={"data": records, "info": {"more_records": False}})
    )


def _backend_users(mock: respx.MockRouter, users: list[dict[str, Any]]) -> None:
    mock.get(f"{_BACKEND_INGEST}/users").mock(return_value=Response(200, json={"items": users}))


async def test_run_is_noop_when_disabled(db_session: AsyncSession, ingest_disabled: None) -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=False) as mock:
        service = await _build_service(db_session, http_client)
        summary = await service.run()

    assert summary.enabled is False
    assert summary.leads_created == 0
    # Nothing was pulled or written when disabled (no upstream call made).
    assert not mock.calls


async def test_run_creates_lead_activity_and_applies_won_deal(
    db_session: AsyncSession, ingest_enabled: None
) -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=False) as mock:
        _backend_users(mock, [{"id": _USER_ID, "email": "rep@example.com"}])
        _module(
            mock,
            "Leads",
            [
                {
                    "id": "ZL1",
                    "Owner": {"email": "rep@example.com"},
                    "Last_Name": "Acme Corp",
                    "Lead_Status": "Qualified",
                    "Lead_Source": "Referral",
                    "Created_Time": "2025-01-15T09:00:00+05:30",
                    "Converted_Deal": {"id": "ZD1"},
                }
            ],
        )
        _module(mock, "Calls", [])
        _module(
            mock,
            "Events",
            [
                {
                    "id": "ZE1",
                    "Owner": {"email": "rep@example.com"},
                    "$se_module": "Leads",
                    "What_Id": {"id": "ZL1"},
                    "Start_DateTime": "2025-02-10T10:00:00+05:30",
                    "End_DateTime": "2025-02-10T10:45:00+05:30",
                    "Location": "Client site, Bhubaneswar",
                }
            ],
        )
        _module(mock, "Tasks", [])
        _module(
            mock,
            "Deals",
            [{"id": "ZD1", "Stage": "Closed Won", "Amount": 50000, "Closing_Date": "2025-03-01"}],
        )
        lead_route = mock.post(f"{_BACKEND_INGEST}/leads").mock(
            return_value=Response(
                201,
                json={"id": _LEAD_ID, "lead_number": "LD-202501-000001", "stage": "QUALIFICATION"},
            )
        )
        activity_route = mock.post(f"{_BACKEND_INGEST}/activities").mock(
            return_value=Response(201, json={"id": _ACTIVITY_ID})
        )
        won_route = mock.patch(f"{_BACKEND_INGEST}/leads/{_LEAD_ID}").mock(
            return_value=Response(
                200, json={"id": _LEAD_ID, "lead_number": "LD-202501-000001", "stage": "WON"}
            )
        )

        service = await _build_service(db_session, http_client)
        summary = await service.run()

    assert summary.leads_created == 1
    assert summary.activities_created == 1
    assert summary.deals_applied == 1
    assert summary.parked == 0
    assert summary.failed == 0

    # Owner resolved to the app user; stage + source mapped; Zoho creation time
    # carried as source_created_at (accurate time-to-close).
    lead_body = json.loads(lead_route.calls.last.request.content)
    assert lead_body["assigned_to_user_id"] == _USER_ID
    assert lead_body["stage"] == "QUALIFICATION"
    assert lead_body["source"] == "REFERENCE"
    assert lead_body["source_created_at"] == "2025-01-15T09:00:00+05:30"

    # A meeting with a Location → VISIT, attributed to the rep, duration computed.
    activity_body = json.loads(activity_route.calls.last.request.content)
    assert activity_body["type"] == "VISIT"
    assert activity_body["rep_user_id"] == _USER_ID
    assert activity_body["lead_id"] == _LEAD_ID
    assert activity_body["duration_minutes"] == 45

    # Won Deal applied to the lead it converted from.
    won_body = json.loads(won_route.calls.last.request.content)
    assert won_body["stage"] == "WON"
    assert won_body["won_value"] == "50000"
    assert won_body["won_at"].startswith("2025-03-01")

    mappings = (await db_session.execute(select(CrmMapping))).scalars().all()
    by_type = {(m.entity_type, m.zoho_id): m.local_id for m in mappings}
    assert by_type[(MappingEntityType.LEAD, "ZL1")] == _LEAD_ID
    assert by_type[(MappingEntityType.ACTIVITY, "ZE1")] == _ACTIVITY_ID
    assert by_type[(MappingEntityType.DEAL, "ZD1")] == _LEAD_ID


async def test_repull_updates_lead_without_duplicate(
    db_session: AsyncSession, ingest_enabled: None
) -> None:
    lead_record = {
        "id": "ZL9",
        "Owner": {"email": "rep@example.com"},
        "Last_Name": "Repeat Co",
        "Lead_Status": "Contacted",
        "Lead_Source": "Phone",
    }

    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=False) as mock:
        _backend_users(mock, [{"id": _USER_ID, "email": "rep@example.com"}])
        _module(mock, "Leads", [lead_record])
        for empty in ("Calls", "Events", "Tasks", "Deals"):
            _module(mock, empty, [])
        create_route = mock.post(f"{_BACKEND_INGEST}/leads").mock(
            return_value=Response(
                201,
                json={"id": _LEAD_ID, "lead_number": "LD-202501-000009", "stage": "QUALIFICATION"},
            )
        )
        update_route = mock.patch(f"{_BACKEND_INGEST}/leads/{_LEAD_ID}").mock(
            return_value=Response(
                200,
                json={"id": _LEAD_ID, "lead_number": "LD-202501-000009", "stage": "QUALIFICATION"},
            )
        )

        service = await _build_service(db_session, http_client)
        first = await service.run()
        second = await service.run()

    assert first.leads_created == 1
    assert second.leads_created == 0
    assert second.leads_updated == 1
    assert create_route.call_count == 1  # created once, never duplicated
    assert update_route.call_count == 1

    lead_mappings = (
        (
            await db_session.execute(
                select(CrmMapping).where(
                    CrmMapping.entity_type == MappingEntityType.LEAD,
                    CrmMapping.zoho_id == "ZL9",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(lead_mappings) == 1


async def test_unmatched_owner_is_parked(db_session: AsyncSession, ingest_enabled: None) -> None:
    async with httpx.AsyncClient() as http_client, respx.mock(assert_all_called=False) as mock:
        _backend_users(mock, [])  # no app users → no email resolves
        _module(
            mock,
            "Leads",
            [{"id": "ZLX", "Owner": {"email": "ghost@example.com"}, "Last_Name": "Orphan"}],
        )
        for empty in ("Calls", "Events", "Tasks", "Deals"):
            _module(mock, empty, [])
        create_route = mock.post(f"{_BACKEND_INGEST}/leads")

        service = await _build_service(db_session, http_client)
        summary = await service.run()

    assert summary.parked == 1
    assert summary.leads_created == 0
    assert not create_route.called  # never wrote an unattributable lead

    parked = (
        (await db_session.execute(select(SyncLog).where(SyncLog.status == SyncStatus.PARKED)))
        .scalars()
        .all()
    )
    assert len(parked) == 1
    assert parked[0].zoho_id == "ZLX"
