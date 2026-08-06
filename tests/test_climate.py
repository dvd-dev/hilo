"""Tests for the Hilo switch platform."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.components.climate.const import ATTR_HVAC_MODE, HVACMode
from homeassistant.const import (
    ATTR_TEMPERATURE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pyhilo.device import HiloDevice
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo.climate import HiloClimate
from custom_components.hilo.const import DOMAIN

from . import setup_with_selected_platforms


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_api")
async def test_climate(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
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
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


def _get_climate_entity(
    hass: HomeAssistant, config_entry: MockConfigEntry, device_name: str
) -> HiloClimate:
    """Return the HiloClimate entity backing the named test fixture device."""
    hilo = hass.data[DOMAIN][config_entry.entry_id]
    device: HiloDevice = next(d for d in hilo.devices.all if d.name == device_name)
    assert isinstance(device._entity, HiloClimate)
    return device._entity


@pytest.mark.usefixtures("mock_api")
async def test_async_set_hvac_mode_heat_writes_heat_not_emergency_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Selecting Heat must never engage the resistive backup strip.

    HILO_MODE_TO_HVAC maps both "heat" and "emergencyheat" to HVACMode.HEAT,
    and the fixture's allowed_modes lists EMERGENCY_HEAT before HEAT
    (["EMERGENCY_HEAT", "HEAT", "OFF", "COOL", "AUTO"], mirroring what Hilo
    actually returns). Picking the first list match therefore used to write
    EMERGENCY_HEAT for a plain Heat request, silently engaging the backup
    strip at several times the running cost.
    """
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 24V")

    with patch.object(
        entity._device, "async_set_low_voltage_state", new=AsyncMock()
    ) as mock_set:
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    mock_set.assert_awaited_once_with(mode="HEAT")


@pytest.mark.usefixtures("mock_api")
async def test_async_set_fan_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """A fan mode change is written through to the device untouched."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 24V")

    with patch.object(
        entity._device, "async_set_low_voltage_state", new=AsyncMock()
    ) as mock_set:
        await entity.async_set_fan_mode("ON")

    mock_set.assert_awaited_once_with(fan_mode="ON")


@pytest.mark.usefixtures("mock_api")
async def test_async_set_temperature_in_cool_mode_sets_cool_setpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """A single setpoint while in COOL must land on the cooling setpoint.

    The fixture device reports Thermostat24VMode: COOL, so its entity is
    already in HVACMode.COOL without any mode switch.
    """
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 24V")
    assert entity.hvac_mode == HVACMode.COOL

    with patch.object(
        entity._device, "async_set_low_voltage_state", new=AsyncMock()
    ) as mock_set:
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 22})

    mock_set.assert_awaited_once_with(cool_setpoint=22)


@pytest.mark.usefixtures("mock_api")
async def test_async_set_temperature_with_hvac_mode_kwarg_switches_then_routes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """climate.set_temperature with an hvac_mode kwarg switches mode first.

    A device currently in HEAT receiving hvac_mode: cool, temperature: 22
    must both switch the device to COOL and route 22 to the cooling
    setpoint, not the heating one.
    """
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 24V")

    with (
        patch.object(
            type(entity._device),
            "low_voltage_mode",
            new_callable=PropertyMock,
            return_value="HEAT",
        ),
        patch.object(
            entity._device, "async_set_low_voltage_state", new=AsyncMock()
        ) as mock_set,
    ):
        assert entity.hvac_mode == HVACMode.HEAT
        await entity.async_set_temperature(
            **{ATTR_HVAC_MODE: HVACMode.COOL, ATTR_TEMPERATURE: 22}
        )

    assert mock_set.await_args_list[0].kwargs == {"mode": "COOL"}
    assert mock_set.await_args_list[-1].kwargs == {"cool_setpoint": 22}


@pytest.mark.usefixtures("mock_api")
async def test_async_set_temperature_baseboard_still_uses_set_attribute(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Baseboard thermostats keep writing through set_attribute, unchanged."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 1")

    with patch.object(entity._device, "set_attribute", new=AsyncMock()) as mock_set:
        await entity.async_set_temperature(**{ATTR_TEMPERATURE: 21})

    mock_set.assert_awaited_once_with("target_temperature", 21)


@pytest.mark.usefixtures("mock_api")
async def test_async_set_hvac_mode_heat_on_baseboard_is_a_silent_noop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """climate.set_hvac_mode: heat on a baseboard device must not log.

    HA validates hvac_mode against hvac_modes before calling in, and heat is
    the only mode a baseboard thermostat ever advertises, so this is a very
    common and perfectly legal automation/scene call. The old class silently
    no-opped it; a warning here would be new log spam for existing users.
    """
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 1")

    caplog.clear()
    await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert "Only heating is available" not in caplog.text


@pytest.mark.usefixtures("mock_api")
async def test_async_set_hvac_mode_cool_on_baseboard_still_warns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A genuinely unsupported mode on a baseboard device keeps its diagnostic."""
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.CLIMATE], mock_api
    )
    entity = _get_climate_entity(hass, mock_config_entry, "Thermostat 1")

    caplog.clear()
    await entity.async_set_hvac_mode(HVACMode.COOL)

    assert "Only heating is available" in caplog.text
