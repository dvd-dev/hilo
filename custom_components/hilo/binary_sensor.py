"""Support for Hilo WebSocket connectivity binary sensor."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import HUB_CHALLENGES, HUB_DEVICES, Hilo
from .const import DOMAIN, LOG, SIGNAL_WEBSOCKET_STATUS
from .entity import HiloEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hilo binary sensor entities."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for d in hilo.devices.all:
        if d.type == "Gateway":
            entities.append(HiloWebSocketStatusSensor(hilo, d))
    async_add_entities(entities)


class HiloWebSocketStatusSensor(HiloEntity, BinarySensorEntity):
    """Binary sensor representing the overall WebSocket connectivity."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, hilo: Hilo, device):
        """Initialize the WebSocket status binary sensor."""
        self._attr_name = "WebSocket Status"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.identifier)}-websocket-status"
        LOG.debug("Setting up WebSocket status binary sensor: %s", self._attr_name)

    @property
    def is_on(self) -> bool:
        """Return True if any WebSocket hub is connected."""
        return any(self._hilo._hub_connected.values())

    @property
    def icon(self) -> str:
        """Return icon based on connectivity state."""
        return "mdi:lan-connect" if self.is_on else "mdi:lan-disconnect"

    @property
    def extra_state_attributes(self) -> dict:
        """Return individual hub connectivity details."""
        return {
            "devices_hub": self._hilo._hub_connected[HUB_DEVICES],
            "challenges_hub": self._hilo._hub_connected[HUB_CHALLENGES],
        }

    async def async_added_to_hass(self) -> None:
        """Register dispatcher listener when added to hass."""
        await super().async_added_to_hass()
        self._unsub_status = async_dispatcher_connect(
            self._hilo._hass,
            SIGNAL_WEBSOCKET_STATUS,
            self._handle_status_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister dispatcher listener when removed."""
        await super().async_will_remove_from_hass()
        self._unsub_status()

    @callback
    def _handle_status_update(self) -> None:
        """Handle connectivity status change from dispatcher."""
        self.async_write_ha_state()
