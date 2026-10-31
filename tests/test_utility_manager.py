"""Tests for the utility meter manager."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.utility_meter.const import DATA_UTILITY, DOMAIN
from homeassistant.core import HomeAssistant

from custom_components.hilo.managers import UtilityManager

TARIFFS = ["low", "medium"]


def _fake_utility_setup(hass: HomeAssistant) -> AsyncMock:
    """Mimic utility_meter.async_setup, which resets its registry of meters."""

    async def setup(hass_arg: HomeAssistant, config: dict) -> bool:
        hass.data[DATA_UTILITY] = {meter: {"new": True} for meter in config[DOMAIN]}
        return True

    return AsyncMock(side_effect=setup)


async def test_existing_meters_are_not_set_up_again(hass: HomeAssistant) -> None:
    """A reload only sets up meters utility_meter doesn't know yet."""
    hass.data[DATA_UTILITY] = {"kitchen_hilo_energy": {"existing": True}}
    manager = UtilityManager(hass, "daily", TARIFFS)
    manager.add_meter("kitchen_hilo_energy", TARIFFS)
    manager.add_meter("office_hilo_energy", TARIFFS)
    fake_setup = _fake_utility_setup(hass)

    with patch("custom_components.hilo.managers.utility_setup", fake_setup):
        await manager.update(MagicMock())

    passed_meters = list(fake_setup.await_args.args[1][DOMAIN])
    assert passed_meters == ["office_hilo_energy"]
    assert hass.data[DATA_UTILITY] == {
        "office_hilo_energy": {"new": True},
        "kitchen_hilo_energy": {"existing": True},
    }


async def test_nothing_new_skips_setup(hass: HomeAssistant) -> None:
    """When every meter already exists, utility_meter is left alone."""
    hass.data[DATA_UTILITY] = {"kitchen_hilo_energy": {"existing": True}}
    manager = UtilityManager(hass, "daily", TARIFFS)
    manager.add_meter("kitchen_hilo_energy", TARIFFS)
    fake_setup = _fake_utility_setup(hass)

    with patch("custom_components.hilo.managers.utility_setup", fake_setup):
        await manager.update(MagicMock())

    fake_setup.assert_not_awaited()
