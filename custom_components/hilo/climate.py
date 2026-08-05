"""Support for Hilo Climate entities."""

from datetime import datetime, timedelta

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PRECISION_TENTHS,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import Hilo
from .const import CLIMATE_CLASSES, DOMAIN, LOG
from .entity import HiloEntity

# Hilo mode vocabulary -> Home Assistant HVAC modes. Keys are normalized
# (lowercase, no separator) so a casing change upstream is tolerated: Hilo
# spells them EMERGENCY_HEAT, HEAT, OFF, COOL and AUTO.
HILO_MODE_TO_HVAC = {
    "off": HVACMode.OFF,
    "heat": HVACMode.HEAT,
    "heating": HVACMode.HEAT,
    "emergencyheat": HVACMode.HEAT,
    "auxheat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "cooling": HVACMode.COOL,
    "auto": HVACMode.HEAT_COOL,
}


def normalize_mode(value) -> str:
    """Normalize a Hilo mode string for lookup purposes."""
    return str(value).strip().lower().replace("_", "").replace(" ", "").replace("-", "")


def validate_reduction_phase(events, tag):
    """Validate if current time is within a challenge lock reduction phase."""
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
    """Set up Hilo climate entities from a config entry."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    entities = []
    for d in hilo.devices.all:
        if d.type in CLIMATE_CLASSES:
            d._entity = HiloClimate(hilo, d)
            entities.append(d._entity)
    async_add_entities(entities)
    return True


class HiloClimate(HiloEntity, ClimateEntity):
    """Representation of a Hilo Climate entity."""

    _attr_temperature_unit: str = UnitOfTemperature.CELSIUS
    _attr_precision: float = PRECISION_TENTHS

    def __init__(self, hilo: Hilo, device):
        """Initialize the climate entity."""
        super().__init__(hilo, device=device, name=device.name)
        old_unique_id = f"{slugify(device.name)}-climate"
        self._attr_unique_id = f"{device.identifier.lower()}-climate"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.CLIMATE
        )
        hilo.async_migrate_unique_id(
            f"{slugify(device.identifier)}-climate",
            self._attr_unique_id,
            Platform.CLIMATE,
        )
        self.operations = [HVACMode.HEAT]
        self._has_operation = False
        self._temperature_entity = None
        LOG.debug("Setting up Climate entity: %s", self._attr_name)

    @property
    def _is_low_voltage(self) -> bool:
        """Whether the device is a 24 V thermostat reporting a real mode.

        getattr() keeps the platform working against an older python-hilo: the
        entity then simply behaves as it did before, heating only.
        """
        return getattr(self._device, "is_low_voltage", False)

    # ------------------------------------------------------------------
    # Temperature
    # ------------------------------------------------------------------
    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.current_temperature

    @property
    def current_humidity(self):
        """Return the ambient humidity, on devices that report it."""
        if not self._is_low_voltage:
            return None
        return self._device.current_humidity

    @property
    def target_temperature(self):
        """Return the target temperature.

        In cooling mode the relevant setpoint is the cooling one; returning the
        heating setpoint would display a value unrelated to what the system is
        actually doing. In auto mode both matter, so the range properties are
        used instead.
        """
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return None
        if self.hvac_mode == HVACMode.COOL:
            cool_setpoint = self._device.cool_setpoint
            if cool_setpoint is not None:
                return cool_setpoint
        return self._device.target_temperature

    @property
    def target_temperature_low(self):
        """Heating setpoint, used in auto mode."""
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._device.target_temperature

    @property
    def target_temperature_high(self):
        """Cooling setpoint, used in auto mode."""
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return self._device.cool_setpoint

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            max_cool = self._device.max_cool_setpoint
            if max_cool is not None:
                return max_cool
        return self._device.max_temp

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        if self.hvac_mode == HVACMode.COOL:
            min_cool = self._device.min_cool_setpoint
            if min_cool is not None:
                return min_cool
        return self._device.min_temp

    # ------------------------------------------------------------------
    # HVAC mode
    # ------------------------------------------------------------------
    @property
    def hvac_modes(self):
        """Return the HVAC modes advertised by the device."""
        if not self._is_low_voltage:
            return [HVACMode.HEAT]
        modes = []
        for raw in self._device.allowed_modes:
            mode = HILO_MODE_TO_HVAC.get(normalize_mode(raw))
            if mode is None:
                LOG.debug(
                    "%s Unknown Hilo thermostat mode %s, ignoring",
                    self._device._tag,
                    raw,
                )
            elif mode not in modes:
                modes.append(mode)
        if not modes:
            # An ordinary thermostat advertises an empty list, and a climate
            # entity with no mode at all is invalid in Home Assistant.
            return [HVACMode.HEAT]
        current = self.hvac_mode
        if current not in modes:
            modes.append(current)
        return modes

    @property
    def hvac_mode(self):
        """Return the current HVAC mode reported by Hilo."""
        if not self._is_low_voltage:
            return HVACMode.HEAT
        raw = self._device.mode
        if raw is None:
            return HVACMode.HEAT
        mode = HILO_MODE_TO_HVAC.get(normalize_mode(raw))
        if mode is None:
            LOG.warning(
                "%s Unknown Hilo thermostat mode %s, falling back to heat",
                self._device._tag,
                raw,
            )
            return HVACMode.HEAT
        return mode

    @property
    def hvac_action(self):
        """Return the current hvac action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return self._device.hvac_action

    # ------------------------------------------------------------------
    # Fan
    # ------------------------------------------------------------------
    @property
    def fan_modes(self):
        """Return the fan modes advertised by the device, if any."""
        if not self._is_low_voltage:
            return None
        return self._device.allowed_fan_modes or None

    @property
    def fan_mode(self):
        """Return the current fan mode, if any."""
        if not self._is_low_voltage:
            return None
        return self._device.fan_mode

    @property
    def supported_features(self):
        """Return the features supported by this particular device."""
        if self.hvac_mode == HVACMode.HEAT_COOL:
            features = ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        else:
            features = ClimateEntityFeature.TARGET_TEMPERATURE
        if self.fan_modes:
            features |= ClimateEntityFeature.FAN_MODE
        modes = self.hvac_modes
        if HVACMode.OFF in modes:
            features |= ClimateEntityFeature.TURN_OFF
            if len(modes) > 1:
                features |= ClimateEntityFeature.TURN_ON
        return features

    @property
    def icon(self):
        """Return the icon to use in the frontend, based on hvac_action."""
        if self.hvac_mode == HVACMode.COOL:
            return "mdi:snowflake"
        if self._device.hvac_action == HVACAction.HEATING:
            return "mdi:radiator"
        return "mdi:radiator-disabled"

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _check_challenge_lock(self) -> None:
        """Block setpoint changes during a Hilo challenge reduction phase."""
        if self._hilo.challenge_lock:
            challenge = self._hilo._hass.states.get("sensor.defi_hilo")
            validate_reduction_phase(
                challenge.attributes.get("next_events", []), self._device._tag
            )

    async def async_set_hvac_mode(self, hvac_mode):
        """Set a new HVAC mode.

        The value sent back is taken from the vocabulary the device advertises,
        so the exact spelling Hilo expects is preserved.
        """
        if not self._is_low_voltage:
            LOG.warning(
                "%s Only heating is available on this device", self._device._tag
            )
            return
        target = next(
            (
                raw
                for raw in self._device.allowed_modes
                if HILO_MODE_TO_HVAC.get(normalize_mode(raw)) == hvac_mode
            ),
            None,
        )
        if target is None:
            raise HomeAssistantError(
                f"Mode {hvac_mode} is not offered by {self._device.name} "
                f"(allowed: {self._device.allowed_modes})"
            )
        LOG.info("%s Setting mode to %s", self._device._tag, target)
        await self._device.async_set_low_voltage_state(mode=target)

    async def async_set_fan_mode(self, fan_mode):
        """Set a new fan mode."""
        LOG.info("%s Setting fan mode to %s", self._device._tag, fan_mode)
        await self._device.async_set_low_voltage_state(fan_mode=fan_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature.

        In heat or cool mode Home Assistant sends a single setpoint, which maps
        to the heating or the cooling one depending on the current mode. In auto
        mode it sends a range, which maps to both at once.
        """
        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        single = kwargs.get(ATTR_TEMPERATURE)

        if low is None and high is None and single is None:
            return

        self._check_challenge_lock()

        if not self._is_low_voltage:
            LOG.info("%s Setting temperature to %s", self._device._tag, single)
            await self._device.set_attribute("target_temperature", single)
            return

        changes = {}
        if low is not None:
            changes["target_temperature"] = low
        if high is not None:
            changes["cool_setpoint"] = high
        if single is not None:
            if self.hvac_mode == HVACMode.COOL:
                changes["cool_setpoint"] = single
            else:
                changes["target_temperature"] = single

        LOG.info("%s Setting temperature: %s", self._device._tag, changes)
        await self._device.async_set_low_voltage_state(**changes)
