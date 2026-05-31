"""Business logic for vendor-item pricing terms.

Owns three invariants on top of the repository:

1. Both ``vendor_id`` and ``item_id`` must point at existing rows
   (404 ``VENDOR_NOT_FOUND`` / ``ITEM_NOT_FOUND`` otherwise).
2. Cross-vendor probing returns 404 (the term's ``vendor_id`` must
   match the URL's ``vendor_id``).
3. No two active terms for the same (vendor, item) may have overlapping
   date ranges (409 ``OVERLAPPING_TERMS``).

Invariant 3 is the headline business rule — see
:meth:`VendorItemTermRepository.find_overlapping_active` for the
predicate.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.vendor_item_term import VendorItemTerm
from app.repositories.item_repo import ItemRepository
from app.repositories.vendor_item_term_repo import VendorItemTermRepository
from app.repositories.vendor_repo import VendorRepository
from app.schemas.vendor_item_term import VendorItemTermCreate, VendorItemTermUpdate

logger = logging.getLogger(__name__)


class VendorItemTermService:
    """Orchestrates vendor-item term flows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._terms = VendorItemTermRepository(session)
        self._vendors = VendorRepository(session)
        self._items = ItemRepository(session)

    async def create(
        self,
        vendor_id: uuid.UUID,
        payload: VendorItemTermCreate,
        *,
        actor_id: uuid.UUID,
    ) -> VendorItemTerm:
        """Create a new term. Validates existence + overlap before insert."""
        if await self._vendors.get_by_id(vendor_id) is None:
            raise NotFoundError("Vendor not found", code="VENDOR_NOT_FOUND")
        if await self._items.get_by_id(payload.item_id) is None:
            raise NotFoundError("Item not found", code="ITEM_NOT_FOUND")

        overlapping = await self._terms.find_overlapping_active(
            vendor_id=vendor_id,
            item_id=payload.item_id,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )
        if overlapping:
            raise ConflictError(
                "An active term already covers part of this date range",
                code="OVERLAPPING_TERMS",
            )

        term = VendorItemTerm(
            vendor_id=vendor_id,
            item_id=payload.item_id,
            rate=payload.rate,
            discount_percent=payload.discount_percent,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            term = await self._terms.add(term)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "Database constraint violation creating term",
                code="DUPLICATE_TERM",
            ) from exc

        logger.info(
            "vendor_term_created",
            extra={
                "term_id": str(term.id),
                "vendor_id": str(term.vendor_id),
                "item_id": str(term.item_id),
            },
        )
        return term

    async def get(self, vendor_id: uuid.UUID, term_id: uuid.UUID) -> VendorItemTerm:
        """Return a term scoped to ``vendor_id``.

        Returns 404 if the term doesn't exist **or** belongs to a
        different vendor. The latter is deliberate — preventing
        cross-vendor probing by term id.
        """
        term = await self._terms.get_by_id(term_id)
        if term is None or term.vendor_id != vendor_id:
            raise NotFoundError("Term not found", code="TERM_NOT_FOUND")
        return term

    async def list_(
        self,
        vendor_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
        item_id: uuid.UUID | None = None,
        active_only: bool = False,
    ) -> tuple[list[VendorItemTerm], int]:
        return await self._terms.list_for_vendor(
            vendor_id=vendor_id,
            limit=limit,
            offset=offset,
            item_id=item_id,
            active_only=active_only,
        )

    async def update(
        self,
        vendor_id: uuid.UUID,
        term_id: uuid.UUID,
        payload: VendorItemTermUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> VendorItemTerm:
        """Apply a partial update.

        The overlap invariant is re-checked using the post-update
        effective range. The date-order invariant is checked at the
        service layer for a clean 422 (the DB CHECK is the final
        backstop).
        """
        term = await self.get(vendor_id, term_id)
        updates = payload.model_dump(exclude_unset=True)

        merged_from: date = updates.get("effective_from", term.effective_from)
        merged_to: date | None = updates.get("effective_to", term.effective_to)
        if merged_to is not None and merged_to < merged_from:
            raise ValidationError(
                "effective_to must be >= effective_from",
                code="INVALID_DATE_RANGE",
            )

        # Re-check overlap only if the resulting term will be active and
        # touches dates. Skip when the update merely deactivates.
        will_be_active = updates.get("is_active", term.is_active)
        if will_be_active:
            overlapping = await self._terms.find_overlapping_active(
                vendor_id=term.vendor_id,
                item_id=term.item_id,
                effective_from=merged_from,
                effective_to=merged_to,
                exclude_id=term.id,
            )
            if overlapping:
                raise ConflictError(
                    "Updated dates overlap with another active term",
                    code="OVERLAPPING_TERMS",
                )

        for field, value in updates.items():
            setattr(term, field, value)
        term.updated_by_user_id = actor_id

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "Database constraint violation on term update",
                code="DUPLICATE_TERM",
            ) from exc
        # ``updated_at`` is server-managed via onupdate; refresh per
        # CLAUDE.md §10.1 so Pydantic's model_validate doesn't trigger
        # sync I/O outside async context.
        await self._session.refresh(term)
        logger.info(
            "vendor_term_updated",
            extra={"term_id": str(term.id), "fields": sorted(updates.keys())},
        )
        return term

    async def deactivate(
        self,
        vendor_id: uuid.UUID,
        term_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
    ) -> None:
        """Soft-delete via ``is_active=False``. Idempotent."""
        term = await self.get(vendor_id, term_id)
        if not term.is_active:
            return  # idempotent no-op
        term.is_active = False
        term.updated_by_user_id = actor_id
        await self._session.commit()
        logger.info(
            "vendor_term_deactivated",
            extra={"term_id": str(term.id), "actor_id": str(actor_id)},
        )
