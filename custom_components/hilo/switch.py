"""Support for Hilo switches."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify
from pyhilo.device.switch import Switch

from . import Hilo
from .const import DOMAIN, LOG, SWITCH_CLASSES
from .entity import HiloEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hilo switches based on a config entry."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for d in hilo.devices.all:
        if d.type in SWITCH_CLASSES:
            d._entity = HiloSwitch(hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)


class HiloSwitch(HiloEntity, SwitchEntity):
    """Representation of a Hilo Switch."""

    def __init__(self, hilo: Hilo, device: Switch):
        """Initialize the switch."""
        super().__init__(hilo, device=device, name=device.name)
        old_unique_id = f"{slugify(device.name)}-switch"
        self._attr_unique_id = f"{slugify(device.identifier)}-switch"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SWITCH
        )
        LOG.debug("Setting up Switch entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the state of the switch."""
        return self._device.state

    @property
    def icon(self):
        """Set the icon based on the switch state."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state == "on":
            return "mdi:power-plug"
        return "mdi:power-plug-off"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self._device.get_value("is_on")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        LOG.info(f"{self._device._tag} Turning off")
        await self._device.set_attribute("is_on", False)
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        LOG.info(f"{self._device._tag} Turning on")
        await self._device.set_attribute("is_on", True)
        self.async_schedule_update_ha_state(True)
