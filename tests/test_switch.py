"""Tests for the Hilo switch platform."""

from unittest.mock import MagicMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo.const import DOMAIN

from . import setup_with_selected_platforms


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the creation, registry entries, and initial states of Hilo switch entities."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_turn_on_and_off(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test toggling switch states via Home Assistant service actions."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )

    entity_id = "switch.smart_plug"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    # Turn the switch on via service call
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_api._set_device_attribute.assert_called_with(
        mock_api._set_device_attribute.call_args[0][0],
        mock_api._set_device_attribute.call_args[0][1],
        True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON
    assert state == snapshot(name=f"{entity_id}-turned-on-state")

    # Turn the switch off via service call
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_api._set_device_attribute.assert_called_with(
        mock_api._set_device_attribute.call_args[0][0],
        mock_api._set_device_attribute.call_args[0][1],
        False,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF
    assert state == snapshot(name=f"{entity_id}-turned-off-state")


@pytest.mark.parametrize(
    ("legacy_unique_id", "expected_unique_id"),
    [
        ("smart_plug-switch", "2a3b4c5d6e7f-switch"),
        ("3a_4b_5c_6d_7e_8f-switch", "3a:4b:5c:6d:7e:8f-switch"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_unique_id_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    legacy_unique_id: str,
    expected_unique_id: str,
) -> None:
    """Test migration of legacy unique IDs (from device name or slugified identifier)."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain=SWITCH_DOMAIN,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
    )
    assert entry.unique_id == legacy_unique_id

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )

    migrated_entry = entity_registry.async_get(entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == expected_unique_id
