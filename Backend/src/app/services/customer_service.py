"""Customer business logic — CRUD orchestration."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.customer import Customer
from app.repositories.customer_repo import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate

logger = logging.getLogger(__name__)


class CustomerService:
    """Orchestrates customer flows on top of :class:`CustomerRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._customers = CustomerRepository(session)

    async def create(self, payload: CustomerCreate, *, actor_id: uuid.UUID) -> Customer:
        """Create a customer. Raises :class:`ConflictError` on duplicate
        ``customer_code`` or ``gstin``.

        The pre-checks give clean error codes in the common case; the
        ``IntegrityError`` catch covers the narrow race window where
        two concurrent requests both pass the pre-check.
        """
        await self._ensure_unique(
            customer_code=payload.customer_code,
            gstin=payload.gstin,
            exclude_id=None,
        )

        customer = Customer(
            company_name=payload.company_name,
            contact_person=payload.contact_person,
            phone=payload.phone,
            email=payload.email,
            address=payload.address,
            is_privileged=payload.is_privileged,
            customer_code=payload.customer_code,
            gstin=payload.gstin,
            notes=payload.notes,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
        try:
            customer = await self._customers.add(customer)
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A customer with that code or GSTIN already exists",
                code="DUPLICATE_CUSTOMER",
            ) from exc

        logger.info("customer_created", extra={"customer_id": str(customer.id)})
        return customer

    async def get(self, customer_id: uuid.UUID) -> Customer:
        customer = await self._customers.get_by_id(customer_id)
        if customer is None:
            raise NotFoundError("Customer not found", code="CUSTOMER_NOT_FOUND")
        return customer

    async def list_(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None = None,
        is_privileged: bool | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Customer], int]:
        return await self._customers.list_(
            limit=limit,
            offset=offset,
            search=search,
            is_privileged=is_privileged,
            is_active=is_active,
        )

    async def update(
        self,
        customer_id: uuid.UUID,
        payload: CustomerUpdate,
        *,
        actor_id: uuid.UUID,
    ) -> Customer:
        """Apply a partial update; raises 409 on uniqueness conflicts."""
        customer = await self.get(customer_id)
        updates = payload.model_dump(exclude_unset=True)

        await self._ensure_unique(
            customer_code=updates.get("customer_code"),
            gstin=updates.get("gstin"),
            exclude_id=customer.id,
        )

        for field, value in updates.items():
            setattr(customer, field, value)
        customer.updated_by_user_id = actor_id

        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(
                "A customer with that code or GSTIN already exists",
                code="DUPLICATE_CUSTOMER",
            ) from exc
        # ``updated_at`` is server-managed via onupdate; refresh so the
        # next attribute read (Pydantic model_validate) doesn't trigger
        # sync I/O outside async context. See CLAUDE.md §10.1.
        await self._session.refresh(customer)
        logger.info(
            "customer_updated",
            extra={"customer_id": str(customer.id), "fields": sorted(updates.keys())},
        )
        return customer

    async def deactivate(self, customer_id: uuid.UUID, *, actor_id: uuid.UUID) -> None:
        """Soft-delete via ``is_active=False``. Idempotent."""
        customer = await self.get(customer_id)
        if not customer.is_active:
            return  # already inactive — no-op, idempotent
        customer.is_active = False
        customer.updated_by_user_id = actor_id
        await self._session.commit()
        logger.info(
            "customer_deactivated",
            extra={"customer_id": str(customer.id), "actor_id": str(actor_id)},
        )

    async def _ensure_unique(
        self,
        *,
        customer_code: str | None,
        gstin: str | None,
        exclude_id: uuid.UUID | None,
    ) -> None:
        """Pre-check uniqueness for ``customer_code`` and ``gstin``.

        ``exclude_id`` lets an UPDATE skip self-conflict. Returns
        ``ConflictError`` with a specific code so the client sees
        ``CUSTOMER_CODE_ALREADY_EXISTS`` or ``GSTIN_ALREADY_EXISTS``
        rather than the generic ``DUPLICATE_CUSTOMER`` from the
        IntegrityError fallback path.
        """
        if customer_code is not None:
            existing = await self._customers.get_by_code(customer_code)
            if existing is not None and existing.id != exclude_id:
                raise ConflictError(
                    "Customer code already in use",
                    code="CUSTOMER_CODE_ALREADY_EXISTS",
                )
        if gstin is not None:
            existing = await self._customers.get_by_gstin(gstin)
            if existing is not None and existing.id != exclude_id:
                raise ConflictError(
                    "GSTIN already in use",
                    code="GSTIN_ALREADY_EXISTS",
                )
