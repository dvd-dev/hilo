"""Tests for the unknown source power tracking."""

from unittest.mock import MagicMock

import pytest

from custom_components.hilo import Hilo


def power_device(
    device_type: str, power: int | None, available: bool = True, model: str = "X"
) -> MagicMock:
    """Return a device reporting the given power."""
    device = MagicMock(type=device_type, available=available, model=model)
    device.has_attribute.side_effect = lambda attribute: attribute == "power"
    device.get_value.return_value = power
    return device


@pytest.mark.parametrize(
    "ignored_device",
    [
        pytest.param(
            power_device("Thermostat", 900, available=False), id="unavailable"
        ),
        pytest.param(
            power_device("Thermostat", 900, model="TH6250WF"), id="unmonitored"
        ),
        pytest.param(power_device("Thermostat", None), id="no_reading_value"),
    ],
)
def test_unknown_power_is_meter_minus_known_devices(
    ignored_device: MagicMock,
) -> None:
    """Test unknown power is the smart meter reading minus the known devices."""
    hilo = Hilo.__new__(Hilo)
    hilo.unknown_tracker_device = power_device("Tracker", 77)
    hilo.devices = MagicMock(
        all=[
            power_device("Meter", 5000),
            power_device("Outlet", 1200),
            ignored_device,
            hilo.unknown_tracker_device,
        ]
    )

    hilo.handle_unknown_power()

    [readings] = hilo.devices.parse_values_received.call_args.args
    assert readings[0]["value"] == 3800


def test_unknown_power_skipped_without_meter_reading() -> None:
    """Test nothing is reported while the smart meter is unavailable."""
    hilo = Hilo.__new__(Hilo)
    hilo.unknown_tracker_device = power_device("Tracker", 77)
    hilo.devices = MagicMock(
        all=[power_device("Meter", 5000, available=False), power_device("Outlet", 1)]
    )

    hilo.handle_unknown_power()

    hilo.devices.parse_values_received.assert_not_called()
