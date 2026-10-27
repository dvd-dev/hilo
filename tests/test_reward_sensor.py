"""Tests for the Hilo reward sensor."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

from custom_components.hilo.sensor import HiloRewardSensor

COMPLETED_EVENT = {"id": 378, "phases": {}, "report": {"status": "Success"}}


async def test_duplicate_event_details_are_ignored(hass: HomeAssistant) -> None:
    """A second details reply for an already processed event does not raise."""
    hilo = MagicMock()
    hilo._hass = hass
    gateway = MagicMock(identifier="gateway123")
    sensor = HiloRewardSensor(hilo, gateway, scan_interval=300)
    sensor._events_to_poll = {378: 2025, 377: 2025}

    await sensor.handle_challenge_details_update(COMPLETED_EVENT)
    await sensor.handle_challenge_details_update(COMPLETED_EVENT)

    assert sensor._events_to_poll == {377: 2025}
