"""Tests for the Hilo switch platform."""

from unittest.mock import MagicMock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
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
    assert state.attributes.get("icon") == "mdi:power-plug-off"

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
    assert state.attributes.get("icon") == "mdi:power-plug"
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
    assert state.attributes.get("icon") == "mdi:power-plug-off"
    assert state == snapshot(name=f"{entity_id}-turned-off-state")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_dynamic_icons(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test dynamic icons based on switch state and availability."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )

    # 1. Unavailable switch -> mdi:lan-disconnect
    unavailable_state = hass.states.get("switch.water_heater_controller")
    assert unavailable_state is not None
    assert unavailable_state.state == STATE_UNAVAILABLE
    assert unavailable_state.attributes.get("icon") == "mdi:lan-disconnect"
    assert unavailable_state == snapshot(name="switch-unavailable-state")

    # 2. On switch -> mdi:power-plug
    on_state = hass.states.get("switch.wall_switch")
    assert on_state is not None
    assert on_state.state == STATE_ON
    assert on_state.attributes.get("icon") == "mdi:power-plug"
    assert on_state == snapshot(name="switch-on-state")

    # 3. Off switch -> mdi:power-plug-off
    off_state = hass.states.get("switch.smart_plug")
    assert off_state is not None
    assert off_state.state == STATE_OFF
    assert off_state.attributes.get("icon") == "mdi:power-plug-off"
    assert off_state == snapshot(name="switch-off-state")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_unique_id_migration_from_name(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test migration of legacy unique ID derived from device name."""
    mock_config_entry.add_to_hass(hass)
    legacy_unique_id = "smart_plug-switch"
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
    assert migrated_entry.unique_id == "2a3b4c5d6e7f-switch"
    assert migrated_entry == snapshot(name="migrated-from-name-entry")


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_switch_unique_id_migration_from_slugified_identifier(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test migration of legacy unique ID derived from slugified identifier."""
    # Pre-register entry using slugified identifier
    mock_config_entry.add_to_hass(hass)
    legacy_unique_id = "3a_4b_5c_6d_7e_8f-switch"
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
    assert migrated_entry.unique_id == "3a:4b:5c:6d:7e:8f-switch"
    assert migrated_entry == snapshot(name="migrated-from-identifier-entry")
