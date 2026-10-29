"""Tests for the Hilo light platform."""

from datetime import timedelta
from unittest.mock import MagicMock

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
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
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo.const import DOMAIN

from . import setup_with_selected_platforms


@pytest.fixture
def device_fixture() -> str:
    """Return fixture file for light platform tests."""
    return "lights.json"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the creation, registry entries, and initial states of Hilo light entities."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_turn_off(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test turning off a light via Home Assistant service action."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )

    entity_id = "light.dimmable_light"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-turned-off-state")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_turn_on(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test turning on a light switch without brightness payload."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )

    entity_id = "light.light_switch"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-turned-on-state")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_turn_on_with_brightness(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test turning on a dimmable light with brightness conversion."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )

    entity_id = "light.white_light"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-turned-on-brightness-state")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_turn_on_with_hs_color(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test turning on a color light with HS color and brightness."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )

    entity_id = "light.color_light"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_HS_COLOR: (240.0, 75.0),
            ATTR_BRIGHTNESS: 200,
        },
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state == snapshot(name=f"{entity_id}-turned-on-hs-color-state")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=2))
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("legacy_unique_id", "expected_unique_id"),
    [
        pytest.param("dimmable_light-light", "6a7b8c9d0e1f-light", id="device_name"),
        pytest.param(
            "7a_8b_9c_0d_1e_2f-light",
            "7a:8b:9c:0d:1e:2f-light",
            id="slugified_identifier",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_light_unique_id_migration(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    legacy_unique_id: str,
    expected_unique_id: str,
) -> None:
    """Test migration of legacy unique IDs (from device name or slugified identifier)."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain=LIGHT_DOMAIN,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
    )
    assert entry.unique_id == legacy_unique_id

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.LIGHT], mock_api
    )

    migrated_entry = entity_registry.async_get(entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == expected_unique_id
    assert migrated_entry == snapshot(name=f"{legacy_unique_id}-migrated-entry")
