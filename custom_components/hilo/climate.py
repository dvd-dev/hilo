from datetime import datetime, timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_TENTHS, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import Hilo, HiloEntity
from .const import CLIMATE_CLASSES, DOMAIN, LOG


def validate_reduction_phase(events, tag):
    if not events:
        return
    current = events[0]
    phases = current["phases"]
    start = phases["reduction_start"]
    end = phases["reduction_end"]
    if (
        start + timedelta(minutes=2)
        < datetime.now(start.tzinfo)
        < end - timedelta(minutes=2)
    ):
        LOG.warning(
            f"{tag} Attempt to set temperature was blocked because challenge lock is active"
        )
        # Raising an exception here will raise it up to the GUI
        raise Exception("Challenge lock is active, unable to change temperature target")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for d in hilo.devices.all:
        if d.type in CLIMATE_CLASSES:
            d._entity = HiloClimate(hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)
    return True


class HiloClimate(HiloEntity, ClimateEntity):
    _attr_hvac_modes = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
    _attr_temperature_unit: str = TEMP_CELSIUS
    _attr_precision: float = PRECISION_TENTHS
    _attr_supported_features: int = SUPPORT_TARGET_TEMPERATURE

    def __init__(self, hilo: Hilo, device):
        super().__init__(hilo, device=device, name=device.name)
        self._attr_unique_id = f"{slugify(device.name)}-climate"
        self.operations = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
        self._has_operation = False
        self._temperature_entity = None
        LOG.debug(f"Setting up Climate entity: {self._attr_name}")

    @property
    def current_temperature(self):
        return self._device.current_temperature

    @property
    def target_temperature(self):
        return self._device.target_temperature

    @property
    def max_temp(self):
        return self._device.max_temp

    @property
    def min_temp(self):
        return self._device.min_temp

    def set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        return

    @property
    def hvac_mode(self):
        return self._device.hvac_mode

    @property
    def icon(self):
        if self._device.hvac_mode == HVAC_MODE_HEAT:
            return "mdi:radiator"
        return "mdi:radiator-disabled"

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            if self._hilo.challenge_lock:
                challenge = self._hilo._hass.states.get("sensor.defi_hilo")
                validate_reduction_phase(
                    challenge.attributes.get("next_events", []), self._device._tag
                )
            LOG.info(
                f"{self._device._tag} Setting temperature to {kwargs[ATTR_TEMPERATURE]}"
            )
            await self._device.set_attribute(
                "target_temperature", kwargs[ATTR_TEMPERATURE]
            )
