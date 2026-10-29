"""Tests for the Hilo sensor platform and EnergySensor entity."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorExtraStoredData,
)
from homeassistant.const import STATE_UNKNOWN, Platform, UnitOfEnergy
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo import SIGNAL_UPDATE_ENTITY
from custom_components.hilo.const import (
    CONF_GENERATE_ENERGY_METERS,
    DOMAIN,
    MAX_SUB_INTERVAL,
)

from . import setup_with_selected_platforms

SMART_PLUG_ENERGY_ENTITY_ID = "sensor.smart_plug_hilo_energy"
SMART_PLUG_DEVICE_ID = 111004


@pytest.fixture(autouse=True)
def freeze_sensor_time(
    freezer: FrozenDateTimeFactory,
    mock_api: MagicMock,
) -> Generator[None]:
    """Freeze time and stub Gateway polling endpoints for deterministic sensor tests."""
    freezer.move_to("2026-10-28T12:00:00Z")
    mock_api.get_seasons = AsyncMock(return_value=[])
    mock_api.get_event_notifications = AsyncMock(return_value=[])
    mock_api.get_weather = AsyncMock(return_value={"temperature": 15})
    with (
        patch(
            "custom_components.hilo.sensor.EnergyManager.init", new_callable=AsyncMock
        ),
        patch(
            "custom_components.hilo.sensor.EnergyManager.update", new_callable=AsyncMock
        ),
        patch(
            "custom_components.hilo.sensor.UtilityManager.update",
            new_callable=AsyncMock,
        ),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry with energy meter generation enabled."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": "hilo", "token": "123"},
        options={CONF_GENERATE_ENERGY_METERS: True},
        unique_id="hilo",
        version=2,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the creation, registry entries, and initial states of Hilo sensor entities."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("legacy_unique_id", "expected_unique_id"),
    [
        pytest.param(
            "hilo_energy_smart_plug",
            "2a3b4c5d6e7f-energy",
            id="device_name",
        ),
        pytest.param(
            "3a_4b_5c_6d_7e_8f-energy",
            "3a:4b:5c:6d:7e:8f-energy",
            id="slugified_identifier",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_unique_id_migration(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_api: MagicMock,
    legacy_unique_id: str,
    expected_unique_id: str,
) -> None:
    """Test migration of legacy energy sensor unique IDs in the entity registry."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
    )

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )

    migrated_entry = entity_registry.async_get(entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == expected_unique_id
    assert migrated_entry == snapshot(name=f"{legacy_unique_id}-migrated-entry")


@pytest.mark.parametrize(
    ("extra_data", "expected_state"),
    [
        pytest.param(
            SensorExtraStoredData(
                native_value=Decimal("42.75"),
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ).as_dict(),
            "42.75",
            id="restores_non_zero_native_value",
        ),
        pytest.param(
            SensorExtraStoredData(
                native_value=Decimal("0.00"),
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ).as_dict(),
            "0.00",
            id="restores_zero_native_value",
        ),
        pytest.param(
            {
                "native_value": None,
                "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "last_valid_state": "19.38",
            },
            "19.38",
            id="restores_legacy_integration_sensor_last_valid_state",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_restore_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    extra_data: dict[str, object],
    expected_state: str,
) -> None:
    """Test EnergySensor restores its cumulative kWh state on startup."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(SMART_PLUG_ENERGY_ENTITY_ID, "0.00"), extra_data)],
    )

    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )

    state = hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_left_riemann_accumulation(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test Left-Riemann integration across idle and active power step changes."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    device = mock_config_entry.runtime_data.devices.find_device(SMART_PLUG_DEVICE_ID)
    assert device is not None

    def push_power(watts: float) -> None:
        device.update(Power={"value": watts})
        async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY.format(device.hilo_id))

    # Initialize baseline at 0 W, then step to 3600 W after 1h -> 0.00 kWh.
    push_power(0)
    freezer.tick(timedelta(hours=1))
    push_power(3600)
    await hass.async_block_till_done()
    assert hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID).state == "0.00"

    # After 30 minutes at 3600 W, step to 1800 W: 3.6 kW * 0.5 h = 1.80 kWh.
    freezer.tick(timedelta(minutes=30))
    push_power(1800)
    await hass.async_block_till_done()
    assert hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID).state == "1.80"

    # After 20 minutes at 1800 W, step to 0 W: +1.8 kW * (1/3 h) = +0.60 -> 2.40 kWh.
    freezer.tick(timedelta(minutes=20))
    push_power(0)
    await hass.async_block_till_done()
    assert hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID) == snapshot(
        name="smart_plug_energy_accumulated_state"
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_sub_cent_precision_across_polls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test small loads accumulate unrounded Decimal precision across frequent polls."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    device = mock_config_entry.runtime_data.devices.find_device(SMART_PLUG_DEVICE_ID)
    assert device is not None
    # 15 W over 60 minutes = 15 Wh = 0.015 kWh (0.00025 kWh per 60s poll).
    device.update(Power={"value": 15})
    device._energy_entity._handle_coordinator_update()

    for _ in range(60):
        freezer.tick(timedelta(minutes=1))
        device._energy_entity._handle_coordinator_update()

    assert device._energy_entity._state == Decimal("0.015")
    assert hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID).state == "0.02"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_max_sub_interval_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test MAX_SUB_INTERVAL timer flushes energy for constant loads without polls."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    device = mock_config_entry.runtime_data.devices.find_device(SMART_PLUG_DEVICE_ID)
    assert device is not None
    # 3600 W for 120s (MAX_SUB_INTERVAL) = 0.12 kWh.
    device.update(Power={"value": 3600})
    async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY.format(device.hilo_id))
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=MAX_SUB_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(SMART_PLUG_ENERGY_ENTITY_ID).state == "0.12"


@pytest.mark.parametrize(
    ("available", "power_value"),
    [
        pytest.param(False, 3600, id="device_offline"),
        pytest.param(True, STATE_UNKNOWN, id="power_state_unknown"),
        pytest.param(True, None, id="power_none"),
        pytest.param(True, "not-a-number", id="power_non_numeric"),
        pytest.param(True, True, id="power_boolean"),
        pytest.param(True, -500, id="power_negative"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_energy_sensor_unavailable_or_invalid_power(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    available: bool,
    power_value: int | str | bool | None,
) -> None:
    """Test unavailable devices or invalid power values do not accumulate phantom energy."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    device = mock_config_entry.runtime_data.devices.find_device(SMART_PLUG_DEVICE_ID)
    assert device is not None
    device.update(Disconnected={"value": not available}, Power={"value": power_value})
    device._energy_entity._handle_coordinator_update()

    freezer.tick(timedelta(hours=1))
    device._energy_entity._handle_coordinator_update()

    assert device._energy_entity.native_value == Decimal("0.00")
