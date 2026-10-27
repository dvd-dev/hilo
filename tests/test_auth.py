"""Tests for the Hilo auth bridge."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from custom_components.hilo.auth import HiloAuth


async def test_access_token_refreshed_before_return() -> None:
    """The session is asked to refresh before its token is read."""
    oauth_session = MagicMock(spec=OAuth2Session)
    oauth_session.async_ensure_token_valid = AsyncMock()
    oauth_session.token = {"access_token": "fresh-token"}

    token = await HiloAuth(oauth_session).async_get_access_token()

    oauth_session.async_ensure_token_valid.assert_awaited_once()
    assert token == "fresh-token"
