"""Vendor business logic — CRUD orchestration.

Mirrors :class:`CustomerService` minus the privileged-tier handling.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.vendor import Vendor
from app.repositories.vendor_repo import VendorRepository
from app.schemas.vendor import VendorCreate, VendorUpdate

logger = logging.getLogger(__name__)


class VendorService:
    """Orchestrates vendor flows on top of :class:`VendorRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._vendors = VendorRepository(session)

    async def create(self, payload: VendorCreate, *, actor_id: uuid.UUID) -> Vendor:
        """Create a vendor. Raises :class:`ConflictError` on duplicate
        ``vendor_code`` or ``gstin``.

        Pre-check gives specific error codes in the common case; the
        ``IntegrityError`` catch covers the race window where two
        concurrent requests both pass the pre-check.
        """
        await self._ensure_unique(
            vendor_code=payload.vendor_code,
            gstin=payload.gstin,
            exclude_id=None,
        )

        vendor = Vendor(
            vendor_name=payload.vendor_name,
            contact_person=payload.contact_person,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            vendor_code=payload.vendor_code,
            gstin=payload.gstin,
            notes=payload.notes,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            vendor = await self._vendors.add(vendor)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A vendor with that code or GSTIN already exists",
                code="DUPLICATE_VENDOR",
            ) from exc

        logger.info("vendor_created", extra={"vendor_id": str(vendor.id)})
        return vendor

    async def get(self, vendor_id: uuid.UUID) -> Vendor:
        vendor = await self._vendors.get_by_id(vendor_id)
        if vendor is None:
            raise NotFoundError("Vendor not found", code="VENDOR_NOT_FOUND")
        return vendor

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Vendor], int]:
        return await self._vendors.list_(
            limit=limit,
            offset=offset,
            search=search,
            is_active=is_active,
        )

    async def update(
        self,
        vendor_id: uuid.UUID,
        payload: VendorUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> Vendor:
        """Apply a partial update; raises 409 on uniqueness conflicts."""
        vendor = await self.get(vendor_id)
        updates = payload.model_dump(exclude_unset=True)

        await self._ensure_unique(
            vendor_code=updates.get("vendor_code"),
            gstin=updates.get("gstin"),
            exclude_id=vendor.id,
        )

        for field, value in updates.items():
            setattr(vendor, field, value)
        vendor.updated_by_user_id = actor_id

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A vendor with that code or GSTIN already exists",
                code="DUPLICATE_VENDOR",
            ) from exc
        # ``updated_at`` is server-managed via onupdate; refresh so the
        # next attribute read (Pydantic model_validate) doesn't trigger
        # sync I/O outside async context. See CLAUDE.md §10.1.
        await self._session.refresh(vendor)
        logger.info(
            "vendor_updated",
            extra={"vendor_id": str(vendor.id), "fields": sorted(updates.keys())},
        )
        return vendor

    async def deactivate(self, vendor_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """Soft-delete via ``is_active=False``. Idempotent."""
        vendor = await self.get(vendor_id)
        if not vendor.is_active:
            return  # already inactive — no-op, idempotent
        vendor.is_active = False
        vendor.updated_by_user_id = actor_id
        await self._session.commit()
        logger.info(
            "vendor_deactivated",
            extra={"vendor_id": str(vendor.id), "actor_id": str(actor_id)},
        )

    async def _ensure_unique(
        self,
        *,
        vendor_code: str | None,
        gstin: str | None,
        exclude_id: uuid.UUID | None,
    ) -> None:
        """Pre-check uniqueness for ``vendor_code`` and ``gstin``.

        ``exclude_id`` lets an UPDATE skip self-conflict. Returns
        :class:`ConflictError` with a specific code so the client sees
        ``VENDOR_CODE_ALREADY_EXISTS`` or ``GSTIN_ALREADY_EXISTS``
        rather than the generic ``DUPLICATE_VENDOR`` from the
        IntegrityError fallback.
        """
        if vendor_code is not None:
            existing = await self._vendors.get_by_code(vendor_code)
            if existing is not None and existing.id != exclude_id:
                raise ConflictError(
                    "Vendor code already in use",
                    code="VENDOR_CODE_ALREADY_EXISTS",
                )
        if gstin is not None:
            existing = await self._vendors.get_by_gstin(gstin)
            if existing is not None and existing.id != exclude_id:
                raise ConflictError(
                    "GSTIN already in use",
                    code="GSTIN_ALREADY_EXISTS",
                )
