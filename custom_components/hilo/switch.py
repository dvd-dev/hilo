from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import Hilo, HiloEntity
from .const import DOMAIN, LOG, SWITCH_CLASSES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for d in hilo.devices.all:
        if d.type in SWITCH_CLASSES:
            d._entity = HiloSwitch(hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)


class HiloSwitch(HiloEntity, SwitchEntity):
    def __init__(self, hilo: Hilo, device):
        super().__init__(hilo, device=device, name=device.name)
        self._attr_unique_id = f"{slugify(device.name)}-switch"
        LOG.debug(f"Setting up Switch entity: {self._attr_name}")

    @property
    def state(self):
        return self._device.state

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state == "on":
            return "mdi:power-plug"
        return "mdi:power-plug-off"

    @property
    def is_on(self):
        return self._device.get_value("is_on")

    async def async_turn_off(self, **kwargs):
        LOG.info(f"{self._device._tag} Turning off")
        await self._device.set_attribute("is_on", False)
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs):
        LOG.info(f"{self._device._tag} Turning on")
        await self._device.set_attribute("is_on", True)
        self.async_schedule_update_ha_state(True)
