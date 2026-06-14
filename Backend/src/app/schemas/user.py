"""User-related Pydantic schemas.

Separate schemas for input (``UserCreate`` / ``UserLogin``) and output
(``UserRead``) so the password hash and any other internal field can
never accidentally leak across the API boundary.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Payload to register a new user."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    full_name: str = Field(min_length=1, max_length=150)
    # min_length = 8 (per project policy).
    # max_length = 128 is a generous upper bound. Argon2 has no input-length
    # limit; this exists only to bound request size and prevent DoS via
    # absurdly long passwords being hashed (Argon2 is intentionally slow).
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Partial update for an existing user.

    Authorization is role-aware and lives in the service layer:

    - **Self** may update ``full_name`` only.
    - **Admin** may update any user's ``full_name``, ``is_active``,
      ``is_admin``.

    ``email`` is deliberately not updatable here — changing email
    needs a verification flow (Phase 2). ``password`` belongs on a
    dedicated change-password endpoint (also Phase 2).

    ``extra="forbid"`` so typos like ``activ`` fail with 422 instead
    of a silent no-op.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_active: bool | None = None
    is_admin: bool | None = None


class UserLogin(BaseModel):
    """Payload to log in an existing user."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    """User as returned to clients.

    Deliberately excludes ``hashed_password`` and any future
    privileged fields. ``from_attributes`` lets us pass an ORM
    instance directly to ``UserRead.model_validate``.

    ``is_admin`` is exposed so the frontend can gate UI elements
    (e.g. show the "Users" admin screen) without making a separate
    permission-probe request.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class UserList(BaseModel):
    """Paginated envelope for admin-only ``GET /users``.

    Shape per ``CLAUDE.md §6``: ``{items, total, limit, offset}``.
    """

    items: list[UserRead]
    total: int
    limit: int
    offset: int


class Token(BaseModel):
    """Bearer-token primitive — issued by ``create_access_token``."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(Token):
    """Body of ``POST /auth/login`` — token plus the authenticated user.

    Including ``user`` here is what lets the frontend skip a separate
    profile bootstrap call after login: it already knows the caller's
    id, role, and active status from the login response. Token shape
    inherits from :class:`Token` so the access-token contract stays in
    one place.
    """

    user: UserRead
