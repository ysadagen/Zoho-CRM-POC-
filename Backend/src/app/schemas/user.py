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

    email: EmailStr
    # min_length = 8 (per project policy).
    # max_length = 128 is a generous upper bound. Argon2 has no input-length
    # limit; this exists only to bound request size and prevent DoS via
    # absurdly long passwords being hashed (Argon2 is intentionally slow).
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Payload to log in an existing user."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    """User as returned to clients.

    Deliberately excludes ``hashed_password`` and any future
    privileged fields. ``from_attributes`` lets us pass an ORM
    instance directly to ``UserRead.model_validate``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    """Bearer-token response body."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
