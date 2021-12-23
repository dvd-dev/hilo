from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_ONOFF,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import Hilo, HiloEntity
from .const import DOMAIN, LIGHT_CLASSES, LOG


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for d in hilo.devices.all:
        if d.type in LIGHT_CLASSES:
            d._entity = HiloLight(hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)


class HiloLight(HiloEntity, LightEntity):
    def __init__(self, hilo: Hilo, device):
        super().__init__(hilo, device=device, name=device.name)
        self._attr_unique_id = f"{slugify(device.name)}-light"
        LOG.debug(f"Setting up Light entity: {self._attr_name}")

    @property
    def brightness(self):
        return self._device.brightness

    @property
    def state(self):
        return self._device.state

    @property
    def is_on(self):
        return self._device.get_value("is_on")

    @property
    def color_mode(self):
        """Return the color mode."""
        return (
            COLOR_MODE_BRIGHTNESS
            if COLOR_MODE_BRIGHTNESS in self.supported_color_modes
            else COLOR_MODE_ONOFF
        )

    @property
    def supported_color_modes(self) -> set:
        """Flag supported modes."""
        supports = set()
        supports.add("onoff")
        if self._device.has_attribute("intensity"):
            supports.add("brightness")
        return supports

    async def async_turn_off(self, **kwargs):
        LOG.info(f"{self._device._tag} Turning off")
        await self._device.set_attribute("is_on", False)
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs):
        LOG.info(f"{self._device._tag} Turning on")
        await self._device.set_attribute("is_on", True)
        if ATTR_BRIGHTNESS in kwargs:
            LOG.info(
                f"{self._device._tag} Setting brightness to {kwargs[ATTR_BRIGHTNESS]}"
            )
            await self._device.set_attribute("intensity", kwargs[ATTR_BRIGHTNESS] / 255)
        self.async_schedule_update_ha_state(True)
