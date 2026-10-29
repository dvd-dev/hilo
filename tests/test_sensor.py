"""Tests for the Hilo EnergySensor entity."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorExtraStoredData,
    SensorStateClass,
)
from homeassistant.const import STATE_UNKNOWN, UnitOfEnergy
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from pyhilo.device import HiloDevice
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.hilo import SIGNAL_UPDATE_ENTITY, Hilo
from custom_components.hilo.const import DOMAIN, HILO_ENERGY_TOTAL, MAX_SUB_INTERVAL
from custom_components.hilo.sensor import EnergySensor


def _create_mock_hilo(hass: HomeAssistant) -> Hilo:
    """Create a lightweight Hilo instance for unit testing."""
    hilo = Hilo.__new__(Hilo)
    hilo._hass = hass
    hilo.coordinator = MagicMock()
    return hilo


def _create_mock_device(
    *,
    name: str = "Kitchen Thermostat",
    device_type: str = "Thermostat",
    identifier: str = "1A:2B:3C:4D:5E:6F",
    hilo_id: str = "urn:hilo:philo:1a2b3c4d5e6f:0",
    power: float | str | bool | None = 0,
    available: bool = True,
) -> MagicMock:
    """Create a mock HiloDevice with configurable power and availability."""
    device = MagicMock(spec=HiloDevice)
    device.name = name
    device.type = device_type
    device.identifier = identifier
    device.hilo_id = hilo_id
    device.manufacturer = "Hilo"
    device.model = "HT402"
    device.gateway_external_id = "100000"
    device.sdi = "1a2b3c4d5e6f"
    device.sw_version = "1.0.0"
    device.available = available
    device.net_consumption = False
    device.get_value.side_effect = lambda attr, default=None: (
        power if attr == "power" else default
    )
    return device


@pytest.mark.parametrize(
    ("device_type", "device_name", "identifier", "expected_name", "expected_unique_id"),
    [
        pytest.param(
            "Thermostat",
            "Kitchen Thermostat",
            "1A2B3C4D5E6F",
            "Kitchen Thermostat Hilo Energy",
            "1a2b3c4d5e6f-energy",
            id="thermostat_device",
        ),
        pytest.param(
            "Meter",
            "SmartEnergyMeter",
            "0x006BAA0000000001-smart_meter",
            HILO_ENERGY_TOTAL,
            "0x006baa0000000001-smart_meter-energy",
            id="smart_meter_device",
        ),
    ],
)
def test_energy_sensor_naming_and_metadata(
    hass: HomeAssistant,
    device_type: str,
    device_name: str,
    identifier: str,
    expected_name: str,
    expected_unique_id: str,
) -> None:
    """Test EnergySensor initializes with expected metadata, unit, and unique ID."""
    hilo = _create_mock_hilo(hass)
    device = _create_mock_device(
        name=device_name,
        device_type=device_type,
        identifier=identifier,
    )

    sensor = EnergySensor(hilo, device)

    assert sensor.name == expected_name
    assert sensor.unique_id == expected_unique_id
    assert sensor.device_class is SensorDeviceClass.ENERGY
    assert sensor.state_class is SensorStateClass.TOTAL_INCREASING
    assert sensor.native_unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR
    assert sensor.suggested_display_precision == 2
    assert sensor.icon == "mdi:lightning-bolt"
    assert sensor.native_value == Decimal("0.00")


@pytest.mark.parametrize(
    ("legacy_unique_id", "expected_unique_id"),
    [
        pytest.param(
            "hilo_energy_kitchen_thermostat",
            "1a:2b:3c:4d:5e:6f-energy",
            id="from_device_name",
        ),
        pytest.param(
            "1a_2b_3c_4d_5e_6f-energy",
            "1a:2b:3c:4d:5e:6f-energy",
            id="from_slugified_identifier",
        ),
    ],
)
def test_energy_sensor_unique_id_migration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    legacy_unique_id: str,
    expected_unique_id: str,
) -> None:
    """Test legacy energy sensor unique_ids are migrated in the entity registry."""
    mock_config_entry.add_to_hass(hass)
    entry = entity_registry.async_get_or_create(
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        unique_id=legacy_unique_id,
        config_entry=mock_config_entry,
    )
    hilo = _create_mock_hilo(hass)
    device = _create_mock_device(
        name="Kitchen Thermostat",
        identifier="1A:2B:3C:4D:5E:6F",
    )

    EnergySensor(hilo, device)

    migrated_entry = entity_registry.async_get(entry.entity_id)
    assert migrated_entry is not None
    assert migrated_entry.unique_id == expected_unique_id


@pytest.mark.parametrize(
    ("extra_data", "expected_value"),
    [
        pytest.param(
            SensorExtraStoredData(
                native_value=Decimal("42.75"),
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ).as_dict(),
            Decimal("42.75"),
            id="restores_non_zero_native_value",
        ),
        pytest.param(
            SensorExtraStoredData(
                native_value=Decimal("0.00"),
                native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            ).as_dict(),
            Decimal("0.00"),
            id="restores_zero_native_value",
        ),
        pytest.param(
            {
                "native_value": None,
                "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                "last_valid_state": "19.38",
            },
            Decimal("19.38"),
            id="restores_legacy_integration_sensor_last_valid_state",
        ),
    ],
)
async def test_energy_sensor_restore_state(
    hass: HomeAssistant,
    extra_data: dict[str, object],
    expected_value: Decimal,
) -> None:
    """Test EnergySensor restores its cumulative kWh state on startup."""
    entity_id = "sensor.kitchen_thermostat_hilo_energy"
    mock_restore_cache_with_extra_data(
        hass,
        [(State(entity_id, "0.00"), extra_data)],
    )
    hilo = _create_mock_hilo(hass)
    device = _create_mock_device(power=0)
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = entity_id

    await sensor.async_added_to_hass()

    assert sensor.native_value == expected_value


async def test_energy_sensor_left_riemann_accumulation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Left-Riemann integration across idle and active power step changes."""
    freezer.move_to("2026-10-28T12:00:00Z")
    hilo = _create_mock_hilo(hass)
    current_power = 0
    device = _create_mock_device(power=0)
    device.get_value.side_effect = lambda attr, default=None: (
        current_power if attr == "power" else default
    )
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = "sensor.kitchen_thermostat_hilo_energy"
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    # After 1 hour at 0 W, heater turns on to 3600 W.
    # Left-Riemann uses the previous 0 W reading over [t0, t0+1h], adding 0 kWh.
    freezer.tick(timedelta(hours=1))
    current_power = 3600
    sensor._handle_coordinator_update()
    assert sensor.native_value == Decimal("0.00")

    # After 30 minutes at 3600 W, power drops to 1800 W: 3.6 kW * 0.5 h = 1.80 kWh.
    freezer.tick(timedelta(minutes=30))
    current_power = 1800
    sensor._handle_coordinator_update()
    assert sensor.native_value == Decimal("1.80")

    # After 20 minutes at 1800 W, heater turns off (0 W): +1.8 kW * (1/3 h) = +0.60 kWh -> 2.40 kWh.
    freezer.tick(timedelta(minutes=20))
    current_power = 0
    sensor._handle_coordinator_update()
    assert sensor.native_value == Decimal("2.40")

    # Another 1 hour at 0 W adds nothing.
    freezer.tick(timedelta(hours=1))
    sensor._handle_coordinator_update()
    assert sensor.native_value == Decimal("2.40")


async def test_energy_sensor_sub_cent_precision_across_polls(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test small loads accumulate unrounded Decimal precision across frequent polls."""
    freezer.move_to("2026-10-28T12:00:00Z")
    hilo = _create_mock_hilo(hass)
    # 15 W over 60 minutes = 15 Wh = 0.015 kWh (0.00025 kWh per 60s poll).
    device = _create_mock_device(power=15)
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = "sensor.kitchen_thermostat_hilo_energy"
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    for _ in range(60):
        freezer.tick(timedelta(minutes=1))
        sensor._handle_coordinator_update()

    assert sensor._state == Decimal("0.015")
    assert sensor.native_value == Decimal("0.02")


async def test_energy_sensor_max_sub_interval_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test MAX_SUB_INTERVAL timer flushes energy for constant loads without polls."""
    freezer.move_to("2026-10-28T12:00:00Z")
    hilo = _create_mock_hilo(hass)
    # 3600 W for 120s (MAX_SUB_INTERVAL) = 0.12 kWh.
    device = _create_mock_device(power=3600)
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = "sensor.kitchen_thermostat_hilo_energy"
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    freezer.tick(timedelta(seconds=MAX_SUB_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert sensor.native_value == Decimal("0.12")
    sensor.async_write_ha_state.assert_called_once()


async def test_energy_sensor_signalr_dispatcher_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test SIGNAL_UPDATE_ENTITY dispatcher triggers immediate integration."""
    freezer.move_to("2026-10-28T12:00:00Z")
    hilo = _create_mock_hilo(hass)
    device = _create_mock_device(
        power=1800,
        hilo_id="urn:hilo:philo:1a2b3c4d5e6f:0",
    )
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = "sensor.kitchen_thermostat_hilo_energy"
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    freezer.tick(timedelta(minutes=10))
    async_dispatcher_send(hass, SIGNAL_UPDATE_ENTITY.format(device.hilo_id))
    await hass.async_block_till_done()

    # 1.8 kW * (10 / 60 h) = 0.30 kWh
    assert sensor.native_value == Decimal("0.30")
    sensor.async_write_ha_state.assert_called_once()


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
async def test_energy_sensor_unavailable_or_invalid_power(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    available: bool,
    power_value: int | str | bool | None,
) -> None:
    """Test unavailable devices or invalid power values do not accumulate phantom energy."""
    freezer.move_to("2026-10-28T12:00:00Z")
    hilo = _create_mock_hilo(hass)
    device = _create_mock_device(power=power_value, available=available)
    sensor = EnergySensor(hilo, device)
    sensor.hass = hass
    sensor.entity_id = "sensor.kitchen_thermostat_hilo_energy"
    sensor.async_write_ha_state = MagicMock()

    await sensor.async_added_to_hass()

    freezer.tick(timedelta(hours=1))
    sensor._handle_coordinator_update()

    assert sensor.native_value == Decimal("0.00")
