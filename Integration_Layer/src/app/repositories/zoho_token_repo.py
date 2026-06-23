"""Data-access layer for ``zoho_tokens`` (single row per provider)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zoho_token import ZOHO_PROVIDER, ZohoToken


class ZohoTokenRepository:
    """Read and upsert the OAuth token row for a single upstream provider."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, provider: str = ZOHO_PROVIDER) -> ZohoToken | None:
        """Return the token row for ``provider``, or ``None`` if not yet stored."""
        stmt = select(ZohoToken).where(ZohoToken.provider == provider)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

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
        """Create or update the single token row for ``provider``.

        Flushes so the caller sees server-side defaults; the surrounding
        service owns the commit.
        """
        token = await self.get(provider=provider)
        if token is None:
            token = ZohoToken(provider=provider)
            self._session.add(token)

        token.access_token = access_token
        token.refresh_token = refresh_token
        token.expires_at = expires_at
        token.token_type = token_type
        token.scope = scope
        token.api_domain = api_domain

        await self._session.flush()
        return token
