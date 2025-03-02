"""Base entity for Hilo."""

from __future__ import annotations

from typing import Union

from homeassistant.const import (
    ATTR_CONNECTIONS,
)
from homeassistant.core import callback
from homeassistant.helpers import (
    device_registry as dr,
)
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from pyhilo.device import HiloDevice
from pyhilo.websocket import WebsocketEvent

from . import SIGNAL_UPDATE_ENTITY, Hilo
from .const import (
    DOMAIN,
)


class HiloEntity(CoordinatorEntity):
    """Define a base Hilo base entity."""

    def __init__(
        self,
        hilo: Hilo,
        name: Union[str, None] = None,
        *,
        device: HiloDevice,
    ) -> None:
        """Initialize."""
        assert hilo.coordinator
        super().__init__(hilo.coordinator)
        device_info_args = {
            "identifiers": {(DOMAIN, device.identifier)},
            "manufacturer": device.manufacturer,
            "model": device.model,
            "name": device.name,
        }
        try:
            device_info_args["via_device"] = (DOMAIN, device.gateway_external_id)
        except AttributeError:
            # If a device doesn't have a gateway_external_id, it's most likely the gateway itself.
            pass  # Do nothing.
        self._attr_device_info = DeviceInfo(**device_info_args)
        try:
            mac_address = dr.format_mac(device.sdi)
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, mac_address)
            }
        except AttributeError:
            pass
        try:
            self._attr_device_info["sw_version"] = device.sw_version
        except AttributeError:
            pass
        if not name:
            name = device.name
        self._attr_name = name
        self._device = device
        self._hilo = hilo
        self._device._entity = self

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._device.available

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        raise NotImplementedError()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._remove_signal_update = async_dispatcher_connect(
            self._hilo._hass,
            SIGNAL_UPDATE_ENTITY.format(self._device.id),
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._remove_signal_update()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        if self._device.type != "Gateway":
            await self.coordinator.async_request_refresh()
