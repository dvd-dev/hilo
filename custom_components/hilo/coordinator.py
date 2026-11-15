"""DataUpdateCoordinator for the Hilo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import LOG

if TYPE_CHECKING:
    from . import Hilo


class HiloCoordinator(DataUpdateCoordinator[None]):
    """Periodically recompute tariff and unknown power state.

    Device state is pushed into python-hilo by SignalR and GraphQL, so this
    coordinator does not fetch it; entities only use it as a refresh tick.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        hilo: Hilo,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOG,
            config_entry=config_entry,
            name="hilo",
            update_interval=update_interval,
        )
        self._hilo = hilo

    async def _async_update_data(self) -> None:
        """Run the periodic tariff and unknown power updates."""
        await self._hilo.async_update()
