"""Test component setup."""

from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hilo.const import CONF_TRACK_UNKNOWN_SOURCES, DOMAIN

from . import setup_with_selected_platforms


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


@pytest.mark.parametrize(
    ("identifier", "expected_success"),
    [
        pytest.param("2a3b4c5d6e7f", False, id="device_still_reported"),
        pytest.param("stale-device", True, id="device_no_longer_reported"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_api: MagicMock,
    identifier: str,
    expected_success: bool,
) -> None:
    """Test only devices no longer reported by Hilo can be removed."""
    assert await async_setup_component(hass, "config", {})
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, identifier)},
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mock_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()

    assert response["success"] is expected_success
    assert (device_registry.async_get(device_entry.id) is None) is expected_success


async def test_remove_config_entry_device_unknown_source_tracker(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the unknown source tracker device cannot be removed while tracked."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TRACK_UNKNOWN_SOURCES: True}
    )
    await setup_with_selected_platforms(hass, mock_config_entry, [], mock_api)
    device_entry = next(
        device
        for device in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        if (DOMAIN, "hass-hilo-unknown_source_tracker") in device.identifiers
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mock_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()

    assert response["success"] is False
    assert device_registry.async_get(device_entry.id) is not None
