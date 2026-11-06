"""Tests for the Hilo custom integration."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import jwt
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

ACCOUNT_EMAIL = "first.account@example.com"


def oauth_token(email: str) -> dict[str, str | int]:
    """Return an OAuth token whose access token identifies the given account."""
    return {
        "access_token": jwt.encode({"email": email}, "secret", algorithm="HS256"),
        "refresh_token": "mock-refresh-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "expires_at": 4102444800,
    }


@pytest.mark.usefixtures("mock_api")
async def setup_with_selected_platforms(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    platforms: list[Platform],
    mock_api: MagicMock,
) -> None:
    """Set up the Hilo integration with the selected platforms."""
    if not hass.config_entries.async_get_entry(entry.entry_id):
        entry.add_to_hass(hass)
    with (
        patch("custom_components.hilo.PLATFORMS", platforms),
        patch("custom_components.hilo.API.async_create", return_value=mock_api),
        patch(
            "custom_components.hilo.Hilo.should_signalr_reconnect",
            new_callable=PropertyMock,
        ) as mock_should_signalr_reconnect,
        patch(
            "custom_components.hilo.GraphQlHelper.async_init", new_callable=AsyncMock
        ),
        patch(
            "custom_components.hilo.GraphQlHelper.subscribe_to_device_updated",
            new_callable=AsyncMock,
        ),
    ):
        mock_should_signalr_reconnect.return_value = False
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
