"""Data-access layer for ``zoho_tokens`` (single row per provider)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zoho_token import ZOHO_PROVIDER, ZohoToken
from app.utils.crypto import decrypt_token, encrypt_token


class ZohoTokenRepository:
    """Read and upsert the OAuth token row for a single upstream provider."""

    def __init__(self, session: AsyncSession, *, encryption_key: str) -> None:
        self._session = session
        self._encryption_key = encryption_key

    async def get(self, *, provider: str = ZOHO_PROVIDER) -> ZohoToken | None:
        """Return the token row for ``provider`` with tokens decrypted in-memory.

        The returned object is expunged from the session so the decrypted values
        are never accidentally flushed back to the database.  Rows written before
        encryption was enabled are returned as-is and will be re-encrypted on the
        next :meth:`upsert`.
        """
        stmt = select(ZohoToken).where(ZohoToken.provider == provider)
        token = (await self._session.execute(stmt)).scalar_one_or_none()
        if token is None:
            return None
        try:
            token.access_token = decrypt_token(token.access_token, self._encryption_key)
            token.refresh_token = decrypt_token(token.refresh_token, self._encryption_key)
        except Exception:
            pass  # pre-encryption rows returned as-is; re-encrypted on next upsert
        self._session.expunge(token)
        return token

    async def upsert(
        self,
        *,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        token_type: str = "Bearer",
        scope: str | None = None,
        api_domain: str | None = None,
        provider: str = ZOHO_PROVIDER,
    ) -> ZohoToken:
        """Create or update the single token row for ``provider``, encrypting tokens.

        Queries the DB directly (not via :meth:`get`) to obtain a live, session-
        tracked object for the update.  Flushes so the caller sees server-side
        defaults; the surrounding service owns the commit.
        """
        stmt = select(ZohoToken).where(ZohoToken.provider == provider)
        token = (await self._session.execute(stmt)).scalar_one_or_none()
        if token is None:
            token = ZohoToken(provider=provider)
            self._session.add(token)

        token.access_token = encrypt_token(access_token, self._encryption_key)
        token.refresh_token = encrypt_token(refresh_token, self._encryption_key)
        token.expires_at = expires_at
        token.token_type = token_type
        token.scope = scope
        token.api_domain = api_domain

        await self._session.flush()
        return token
