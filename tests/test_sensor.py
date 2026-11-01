"""Tests for the Hilo sensor platform."""

from unittest.mock import MagicMock

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo.const import DOMAIN

from . import setup_with_selected_platforms

HUMIDITY_ENTITY_ID = "sensor.thermostat_1_humidity"
HUMIDITY_UNIQUE_ID = "1a2b3c4d5e6f-humidity"


@pytest.mark.parametrize("ambient_humidity", [45])
async def test_humidity_sensor(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_api: MagicMock,
    graphql_location: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    """A thermostat with a GraphQL humidity reading gets a humidity sensor."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api, graphql_location
    )

    assert entity_registry.async_get(HUMIDITY_ENTITY_ID) == snapshot(name="entry")
    assert hass.states.get(HUMIDITY_ENTITY_ID) == snapshot(name="state")


async def test_no_humidity_sensor_without_reading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    graphql_location: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    """A thermostat reporting 0 humidity (no sensor, e.g. HT402) gets no sensor."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api, graphql_location
    )

    assert (
        entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, HUMIDITY_UNIQUE_ID)
        is None
    )


@pytest.mark.parametrize("ambient_humidity", [45])
async def test_humidity_sensor_unknown_when_reading_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    graphql_location: dict[str, dict[str, list[dict[str, object]]]],
) -> None:
    """A humidity sensor whose reading later goes missing reports unknown."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api, graphql_location
    )
    hilo = mock_config_entry.runtime_data

    hilo.devices.parse_values_received(
        [
            {
                "deviceId": 111000,
                "locationId": 123,
                "timeStampUTC": "2026-11-01T12:00:00Z",
                "attribute": "Humidity",
                "valueType": "Percentage",
                "value": None,
            }
        ]
    )
    await hilo.coordinator.async_refresh()

    state = hass.states.get(HUMIDITY_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
