"""Token service — get-or-refresh the Zoho access token, with persistence.

Orchestrates the OAuth client and the token repository so the rest of the app
asks only for "a valid access token". The live access token and its expiry are
persisted in ``zoho_tokens``; the refresh token comes from that row once it
exists, falling back to the bootstrap ``ZOHO_REFRESH_TOKEN`` setting on first
use (Zoho's refresh grant returns no new refresh token, so the same one
persists across refreshes).

A small expiry skew triggers a proactive refresh *before* the token actually
lapses, so a request never races the boundary and fails with a 401.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.zoho.errors import ZohoAuthError
from app.clients.zoho.oauth import ZohoOAuthClient
from app.core.config import Settings
from app.repositories.zoho_token_repo import ZohoTokenRepository

logger = logging.getLogger(__name__)

# Refresh this many seconds before the stored expiry to avoid boundary races.
_EXPIRY_SKEW_SECONDS = 60


class TokenService:
    """Provide a valid Zoho access token, refreshing and persisting as needed."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        oauth_client: ZohoOAuthClient,
        settings: Settings,
    ) -> None:
        self._session = session
        self._repo = ZohoTokenRepository(session)
        self._oauth = oauth_client
        self._settings = settings

    async def get_access_token(self) -> str:
        """Return a valid access token, refreshing only if missing or near expiry."""
        token = await self._repo.get()
        if token is not None and not self._is_expiring(token.expires_at):
            return token.access_token
        return await self.force_refresh()

    async def force_refresh(self) -> str:
        """Refresh the access token unconditionally and persist the new state.

        Uses the persisted refresh token when present, else the bootstrap
        setting. Raises :class:`ZohoAuthError` (via the OAuth client) if Zoho
        rejects the refresh token or client credentials.
        """
        existing = await self._repo.get()
        refresh_token = existing.refresh_token if existing else self._settings.zoho_refresh_token
        if not refresh_token:
            raise ZohoAuthError("No Zoho refresh token available (bootstrap or stored)")

        response = await self._oauth.refresh(refresh_token)
        expires_at = datetime.now(UTC) + timedelta(seconds=response.expires_in)

        await self._repo.upsert(
            access_token=response.access_token,
            # Carry the refresh token forward — the grant does not reissue one.
            refresh_token=refresh_token,
            expires_at=expires_at,
            token_type=response.token_type,
            scope=response.scope,
            api_domain=response.api_domain,
        )
        await self._session.commit()
        return response.access_token

    @staticmethod
    def _is_expiring(expires_at: datetime) -> bool:
        """True if ``expires_at`` is within the refresh skew of now (UTC)."""
        threshold = datetime.now(UTC) + timedelta(seconds=_EXPIRY_SKEW_SECONDS)
        return expires_at <= threshold
