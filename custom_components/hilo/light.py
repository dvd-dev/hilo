from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
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
            d._entity = HiloLight(hass, hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)


class HiloLight(HiloEntity, LightEntity):
    def __init__(self, hass: HomeAssistant, hilo: Hilo, device):
        super().__init__(hilo, device=device, name=device.name)
        self._attr_unique_id = f"{slugify(device.name)}-light"
        self._debounced_turn_on = Debouncer(
            hass,
            LOG,
            cooldown=1,
            immediate=True,
            function=self._async_debounced_turn_on,
        )
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
    def hs_color(self):
        return (self._device.hue, self._device.saturation)

    @property
    def color_mode(self):
        """Return the color mode."""
        if ColorMode.HS in self.supported_color_modes:
            return ColorMode.HS
        elif ColorMode.BRIGHTNESS in self.supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def supported_color_modes(self) -> set:
        """Flag supported modes."""
        supports = set()
        supports.add(ColorMode.ONOFF)
        if self._device.has_attribute("intensity"):
            supports.add(ColorMode.BRIGHTNESS)
        if self._device.has_attribute("hue"):
            supports.add(ColorMode.HS)
        return supports

    async def async_turn_off(self, **kwargs):
        LOG.info(f"{self._device._tag} Turning off")
        await self._device.set_attribute("is_on", False)
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs):
        self._last_kwargs = kwargs
        await self._debounced_turn_on.async_call()

    async def _async_debounced_turn_on(self):
        LOG.info(f"{self._device._tag} Turning on")
        await self._device.set_attribute("is_on", True)
        if ATTR_BRIGHTNESS in self._last_kwargs:
            LOG.info(
                f"{self._device._tag} Setting brightness to {self._last_kwargs[ATTR_BRIGHTNESS]}"
            )
            await self._device.set_attribute(
                "intensity", self._last_kwargs[ATTR_BRIGHTNESS] / 255
            )
        if ATTR_HS_COLOR in self._last_kwargs:
            LOG.info(
                f"{self._device._tag} Setting HS Color to {self._last_kwargs[ATTR_HS_COLOR]}"
            )
            await self._device.set_attribute("hue", self._last_kwargs[ATTR_HS_COLOR][0])
            await self._device.set_attribute(
                "saturation", self._last_kwargs[ATTR_HS_COLOR][1]
            )
        self.async_schedule_update_ha_state(True)
