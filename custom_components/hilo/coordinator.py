"""DataUpdateCoordinator for the Hilo integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyhilo.devices import Devices

from .const import LOG

if TYPE_CHECKING:
    from . import Hilo


class HiloCoordinator(DataUpdateCoordinator[Devices]):
    """Notify entities when SignalR or GraphQL push new device values.

    python-hilo already holds the device state, so nothing is polled here.
    A failure means the SignalR device hub is down and values are stale.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        hilo: Hilo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, LOG, config_entry=config_entry, name="hilo")
        self._hilo = hilo

    async def _async_update_data(self) -> Devices:
        """Return the device state python-hilo keeps up to date."""
        return self._hilo.devices
