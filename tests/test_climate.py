"""Tests for the Hilo climate platform."""

from unittest.mock import MagicMock

from homeassistant.const import (
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from . import setup_with_selected_platforms


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the creation and values of the Hilo Climate."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert entity_entries
    for entity_entry in entity_entries:
        # TODO: Consider reverting to syrupy snapshot testing once support for
        # Python 3.13 (Home Assistant < 2026.3) is dropped. In HA 2026.3+, internal
        # EntityRegistryEntry capability dictionary keys changed from strings
        # ('hvac_modes') to enum members (ClimateEntityCapabilityAttribute.HVAC_MODES),
        # causing snapshot comparisons to diverge across supported HA versions.
        # Direct property assertions test the integration behavior reliably across both.
        assert entity_entry.domain == "climate"
        assert entity_entry.platform == "hilo"
        assert entity_entry.unique_id == "1a2b3c4d5e6f-climate"
        assert entity_entry.original_name == "Thermostat 1"
        assert entity_entry.original_icon == "mdi:radiator-disabled"

        state = hass.states.get(entity_entry.entity_id)
        assert state is not None
        assert state.state == "unavailable"
        assert state.attributes.get("friendly_name") == "Thermostat 1"
        assert state.attributes.get("icon") == "mdi:radiator-disabled"
        assert state.attributes.get("min_temp") == 5.0
        assert state.attributes.get("max_temp") == 36.0
