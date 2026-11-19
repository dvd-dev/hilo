"""Tests for the Hilo custom integration."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.mark.usefixtures("mock_api")
async def setup_with_selected_platforms(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    platforms: list[Platform],
    mock_api: MagicMock,
    graphql_location: dict[str, dict[str, list[dict[str, object]]]] | None = None,
) -> None:
    """Set up the Hilo integration with the selected platforms.

    When given, graphql_location is handled as the getLocation query result,
    which is where python-hilo loads device readings such as humidity.
    """
    if not hass.config_entries.async_get_entry(entry.entry_id):
        entry.add_to_hass(hass)
    graphql_init = (
        patch(
            "custom_components.hilo.GraphQlHelper.async_init",
            autospec=True,
            side_effect=lambda helper: helper._handle_query_result(graphql_location),
        )
        if graphql_location is not None
        else patch(
            "custom_components.hilo.GraphQlHelper.async_init", new_callable=AsyncMock
        )
    )
    with (
        patch("custom_components.hilo.PLATFORMS", platforms),
        patch("custom_components.hilo.API.async_create", return_value=mock_api),
        patch(
            "custom_components.hilo.Hilo.should_signalr_reconnect",
            new_callable=PropertyMock,
        ) as mock_should_signalr_reconnect,
        graphql_init,
        patch(
            "custom_components.hilo.GraphQlHelper.subscribe_to_device_updated",
            new_callable=AsyncMock,
        ),
    ):
        mock_should_signalr_reconnect.return_value = False
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
