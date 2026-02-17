"""Hilo Light platform integration."""

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_HS_COLOR, LightEntity
from homeassistant.components.light.const import ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import Hilo
from .const import DOMAIN, LIGHT_CLASSES, LOG
from .entity import HiloEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hilo light entities from a config entry."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for d in hilo.devices.all:
        if d.type in LIGHT_CLASSES:
            d._entity = HiloLight(hass, hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)


class HiloLight(HiloEntity, LightEntity):
    """Define a Hilo Light entity."""

    def __init__(self, hass: HomeAssistant, hilo: Hilo, device):
        """Initialize the Hilo light entity."""
        super().__init__(hilo, device=device, name=device.name)
        old_unique_id = f"{slugify(device.name)}-light"
        self._attr_unique_id = f"{slugify(device.identifier)}-light"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.LIGHT
        )
        self._debounced_turn_on = Debouncer(
            hass,
            LOG,
            cooldown=1,
            immediate=True,
            function=self._async_debounced_turn_on,
        )
        LOG.debug("Setting up Light entity: %s", self._attr_name)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._device.brightness

    @property
    def state(self):
        """Return the state of the light."""
        return self._device.state

    @property
    def is_on(self):
        """Return whether the light is on."""
        return self._device.get_value("is_on")

    @property
    def hs_color(self):
        """Return the HS color."""
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
        color_modes = set()
        if self._device.has_attribute("hue"):
            color_modes.add(ColorMode.HS)
        if not color_modes and self._device.has_attribute("intensity"):
            color_modes.add(ColorMode.BRIGHTNESS)
        if not color_modes:
            color_modes.add(ColorMode.ONOFF)
        return color_modes

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""
        LOG.info(f"{self._device._tag} Turning off")
        await self._device.set_attribute("is_on", False)
        self.async_schedule_update_ha_state(True)

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""
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
