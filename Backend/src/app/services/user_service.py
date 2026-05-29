"""User business logic — registration and authentication.

Services own transaction boundaries and emit domain exceptions. The
route layer never catches these; the global :class:`AppError` handler
in ``app.main`` maps them to a consistent JSON envelope.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.user import Token, UserCreate, UserLogin

logger = logging.getLogger(__name__)


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
            hashed_password=hash_password(payload.password),
        )
        await self._session.commit()
        logger.info("user_registered", extra={"user_id": str(user.id)})
        return user

    async def authenticate(self, payload: UserLogin) -> Token:
        """Verify credentials and issue a bearer token.

        Returns the same :class:`AuthenticationError` (``INVALID_CREDENTIALS``)
        for both unknown email and wrong password so the API does not
        leak which emails are registered.
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
        token, expires_in = create_access_token(user.id)
        logger.info("user_authenticated", extra={"user_id": str(user.id)})
        return Token(access_token=token, expires_in=expires_in)
