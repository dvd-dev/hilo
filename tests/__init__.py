"""Tests for the Hilo custom integration."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api")
async def setup_with_selected_platforms(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    platforms: list[Platform],
    mock_api: MagicMock,
) -> None:
    """Set up the Hilo integration with the selected platforms."""
    entry.add_to_hass(hass)
    with (
        patch("custom_components.hilo.PLATFORMS", platforms),
        patch("custom_components.hilo.API.async_create", return_value=mock_api),
        patch(
            "custom_components.hilo.Hilo.should_websocket_reconnect",
            new_callable=PropertyMock,
        ) as mock_should_websocket_reconnect,
    ):
        mock_should_websocket_reconnect.return_value = False
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
