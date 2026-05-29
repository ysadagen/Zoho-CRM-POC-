"""User business logic — registration, authentication, admin lifecycle.

Services own transaction boundaries and emit domain exceptions. The
route layer never catches these; the global :class:`AppError` handler
in ``app.main`` maps them to a consistent JSON envelope.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import Token, UserCreate, UserLogin, UserUpdate

logger = logging.getLogger(__name__)

# Fields only an admin may change via PATCH. Used by ``update_user`` to
# raise 403 if a non-admin tries to sneak them through the body.
_ADMIN_ONLY_UPDATE_FIELDS: frozenset[str] = frozenset({"is_active", "is_admin"})


class UserService:
    """Orchestrates user-facing flows on top of :class:`UserRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def register(self, payload: UserCreate) -> User:
        """Create a new user.

        Raises :class:`ConflictError` (409) if a user with this email
        already exists. Email comparison is case-insensitive — the value
        is lowercased before lookup and storage.
        """
        email = payload.email.lower()
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise ConflictError(
                "A user with that email already exists",
                code="EMAIL_ALREADY_REGISTERED",
            )
        user = await self._users.create(
            email=email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
        )
        await self._session.commit()
        logger.info("user_registered", extra={"user_id": str(user.id)})
        return user

    async def list_users(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        """List all users. Authorization is enforced at the route layer
        via ``require_admin`` — this method is intentionally unaware of
        roles so the same call would compose into a future admin
        dashboard or report without modification.
        """
        return await self._users.list_(limit=limit, offset=offset)

    async def update_user(
        self,
        user_id: uuid.UUID,
        payload: UserUpdate,
        *,
        actor: User,
    ) -> User:
        """Apply a partial update to a user, with role-aware authorization.

        - **Self**: may update own ``full_name`` only.
        - **Admin**: may update any user's ``full_name``, ``is_active``,
          ``is_admin``.
        - **Non-admin targeting another user**: raises
          :class:`NotFoundError` (404) so the API does not let callers
          enumerate user ids by probing — same rule as :func:`get_user`.
        - **Non-admin sending privileged fields**
          (``is_active``/``is_admin``): raises :class:`AuthorizationError`
          (403, ``ADMIN_REQUIRED``).
        """
        is_self = actor.id == user_id

        if not actor.is_admin and not is_self:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")

        updates = payload.model_dump(exclude_unset=True)

        if not actor.is_admin and _ADMIN_ONLY_UPDATE_FIELDS & updates.keys():
            raise AuthorizationError(
                "Admin role required to change is_active or is_admin",
                code="ADMIN_REQUIRED",
            )

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")

        for field, value in updates.items():
            setattr(user, field, value)

        await self._session.commit()
        # ``updated_at`` is server-managed; refresh so the next attribute
        # read doesn't trigger sync I/O outside async context.
        await self._session.refresh(user)
        logger.info(
            "user_updated",
            extra={
                "user_id": str(user.id),
                "actor_id": str(actor.id),
                "fields": sorted(updates.keys()),
            },
        )
        return user

    async def deactivate_user(
        self,
        user_id: uuid.UUID,
        *,
        actor: User,
    ) -> None:
        """Soft-delete a user by setting ``is_active=False``.

        Caller authorization (admin-only) is enforced at the route
        layer via ``require_admin``. This service additionally
        prevents an admin from deactivating their **own** account —
        that would log the admin out mid-session and could orphan the
        system if it was the only admin.

        Hard delete is intentionally unsupported: ``items`` reference
        users via FK with ``ON DELETE RESTRICT``, so keeping the row
        preserves the audit trail.
        """
        if actor.id == user_id:
            raise ConflictError(
                "Admins cannot deactivate their own account",
                code="CANNOT_DEACTIVATE_SELF",
            )

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found", code="USER_NOT_FOUND")

        if not user.is_active:
            # Already deactivated — idempotent no-op rather than 409.
            return

        user.is_active = False
        await self._session.commit()
        logger.info(
            "user_deactivated",
            extra={"user_id": str(user.id), "actor_id": str(actor.id)},
        )

    async def authenticate(self, payload: UserLogin) -> tuple[User, Token]:
        """Verify credentials and issue a bearer token.

        Returns the authenticated :class:`User` plus the issued
        :class:`Token` so the route can compose whichever response
        shape it needs (currently :class:`LoginResponse`).

        Raises :class:`AuthenticationError` with the same
        ``INVALID_CREDENTIALS`` code for both unknown email and wrong
        password so the API does not leak which emails are registered.
        """
        email = payload.email.lower()
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(payload.password, user.hashed_password):
            raise AuthenticationError(
                "Invalid email or password",
                code="INVALID_CREDENTIALS",
            )
        if not user.is_active:
            raise AuthenticationError(
                "User account is disabled",
                code="ACCOUNT_DISABLED",
            )
        access_token, expires_in = create_access_token(user.id)
        logger.info("user_authenticated", extra={"user_id": str(user.id)})
        return user, Token(access_token=access_token, expires_in=expires_in)
