"""Tests for the legacy gateway identifier lookup."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hilo import Hilo
from custom_components.hilo.const import DOMAIN

GATEWAY_MAC = "aa:bb:cc:dd:ee:ff"


def _add_legacy_gateway(
    device_registry: dr.DeviceRegistry, entry: MockConfigEntry, dsn: str
) -> None:
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, dsn)},
        manufacturer="Hilo",
        model="EQ000017",
    )


async def test_legacy_gateway_of_other_entry_is_ignored(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Only this entry's gateway is a migration candidate."""
    entry = MockConfigEntry(domain=DOMAIN)
    other_entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)
    _add_legacy_gateway(device_registry, other_entry, "other-dsn")
    hilo = MagicMock(_hass=hass, entry=entry)

    assert await Hilo._fetch_legacy_gateway_dsn(hilo, GATEWAY_MAC) is None


async def test_legacy_gateway_of_this_entry_is_found(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The entry's own DSN-based gateway is returned for migration."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    _add_legacy_gateway(device_registry, entry, "own-dsn")
    hilo = MagicMock(_hass=hass, entry=entry)

    assert await Hilo._fetch_legacy_gateway_dsn(hilo, GATEWAY_MAC) == "own-dsn"
