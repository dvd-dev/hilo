"""Support for various Hilo sensors."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.integration.sensor import (
    TRAPEZOIDAL_METHOD,
    IntegrationSensor,
)
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, slugify
import homeassistant.util.dt as dt_util
from pyhilo.device import HiloDevice
from pyhilo.util.hilo import event_parsing

from . import Hilo, HiloEntity
from .const import (
    CONF_ENERGY_METER_PERIOD,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_TARIFF,
    DEFAULT_ENERGY_METER_PERIOD,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HILO_ENERGY_TOTAL,
    HILO_SENSOR_CLASSES,
    LOG,
)
from .managers import EnergyManager, UtilityManager


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hilo sensors based on a config entry."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    new_entities = []
    cost_entities = []
    hq_plan_name = entry.options.get(CONF_HQ_PLAN_NAME, DEFAULT_HQ_PLAN_NAME)
    energy_meter_period = entry.options.get(
        CONF_ENERGY_METER_PERIOD, DEFAULT_ENERGY_METER_PERIOD
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    generate_energy_meters = entry.options.get(
        CONF_GENERATE_ENERGY_METERS, DEFAULT_GENERATE_ENERGY_METERS
    )
    if generate_energy_meters:
        energy_manager = await EnergyManager().init(hass, energy_meter_period)
        utility_manager = UtilityManager(energy_meter_period)

    def create_energy_entity(device):
        device._energy_entity = EnergySensor(device)
        new_entities.append(device._energy_entity)
        energy_entity = f"hilo_energy_{slugify(device.name)}"
        if energy_entity == HILO_ENERGY_TOTAL:
            LOG.error(
                "An hilo entity can't be named 'total' because it conflicts "
                "with the generated name for the smart energy meter"
            )
            return
        if device.type == "Meter":
            energy_entity = HILO_ENERGY_TOTAL
        utility_manager.add_meter(energy_entity)
        energy_manager.add_to_dashboard(energy_entity)

    for d in hilo.devices.all:
        LOG.debug(f"Adding device {d}")
        if d.type == "Gateway":
            new_entities.append(
                HiloChallengeSensor(hilo, d, scan_interval),
            )
        if d.type == "Thermostat":
            d._temperature_entity = TemperatureSensor(hilo, d)
            new_entities.append(d._temperature_entity)
        elif d.type in HILO_SENSOR_CLASSES:
            d._device_sensor_entity = DeviceSensor(hilo, d)
            new_entities.append(d._device_sensor_entity)
        if d.has_attribute("power"):
            d._power_entity = PowerSensor(hilo, d)
            new_entities.append(d._power_entity)
            # If we opt out the geneneration of meters we just create the power sensors
            if generate_energy_meters:
                create_energy_entity(d)

    async_add_entities(new_entities)
    if not generate_energy_meters:
        return
    # Creating cost sensors based on plan
    # This will generate hilo_cost_(low|medium|high) sensors which can be
    # referred later in the energy dashboard based on the tarif selected
    for tarif, amount in CONF_TARIFF.get(hq_plan_name).items():
        sensor_name = f"hilo_rate_{tarif}"
        cost_entities.append(HiloCostSensor(sensor_name, hq_plan_name, amount))
    cost_entities.append(HiloCostSensor("hilo_rate_current", hq_plan_name))
    async_add_entities(cost_entities)
    # This setups the utility_meter platform
    await utility_manager.update(hass, async_add_entities)
    # This sends the entities to the energy dashboard
    await energy_manager.update()


class TemperatureSensor(HiloEntity, SensorEntity):
    """Define a Hilo temperature sensor entity."""

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Temperature"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-temperature"
        LOG.debug(f"Setting up TemperatureSensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(int(self._device.current_temperature))


class HiloChallengeSensor(HiloEntity, SensorEntity):

    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Defi Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = slugify(self._attr_name)
        LOG.debug(f"Setting up ChallengeSensor entity: {self._attr_name}")
        self.scan_interval = timedelta(seconds=scan_interval)
        self._state = "off"
        self._next_events = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if self.state == "off":
            return "mdi:lightning-bolt"
        elif self.state == "scheduled":
            return "mdi:progress-clock"
        elif self.state == "pre_heat":
            return "mdi:radiator"
        elif self.state in ["reduction", "on"]:
            return "mdi:power-plug-off"
        elif self.state == "recovery":
            return "mdi:calendar-check"
        return "mdi:battery-alert"

    @property
    def should_poll(self):
        return True

    @property
    def extra_state_attributes(self):
        return {"next_events": self._next_events}

    async def _async_update(self):
        self._next_events = []
        events = await self._hilo._api.get_events(self._hilo.devices.location_id)
        for raw_event in events:
            event = event_parsing(raw_event)
            if not event:
                continue
            self._next_events.append(event)
        self._state = "off"
        if len(self._next_events):
            self._state = self._next_events[0]["current"]


class DeviceSensor(HiloEntity, SensorEntity):
    """Devices like the gateway or Smoke Detectors don't have much attributes,
    except for the "disonnected" attributes. These entities are monitoring
    this state.
    """

    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, hilo, device):
        self._attr_name = device.name
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = slugify(device.name)
        LOG.debug(f"Setting up DeviceSensor entity: {self._attr_name}")

    @property
    def state(self):
        return "on" if self._device.available else "off"

    @property
    def icon(self):
        if self.state == "off":
            return "mdi:access-point-network-off"
        return "mdi:access-point-network"


class PowerSensor(HiloEntity, SensorEntity):
    """Define a Hilo power sensor entity."""

    _attr_device_class = DEVICE_CLASS_POWER
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo: Hilo, device: HiloDevice) -> None:
        """Initialize."""
        self._attr_name = f"{device.name} Power"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-power"
        LOG.debug(f"Setting up PowerSensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(int(self._device.get_value("power", 0)))


class EnergySensor(IntegrationSensor):
    """Define a Hilo energy sensor entity."""

    _attr_device_class = DEVICE_CLASS_ENERGY
    _attr_native_unit_of_measurement = ENERGY_WATT_HOUR
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, device):
        self._device = device
        self._attr_name = f"hilo_energy_{slugify(device.name)}"
        self._unit_of_measurement = ENERGY_WATT_HOUR
        self._unit_prefix = None
        if device.type == "Meter":
            self._attr_name = HILO_ENERGY_TOTAL
            self._unit_of_measurement = ENERGY_KILO_WATT_HOUR
            self._unit_prefix = "k"
        if device.type == "Thermostat":
            self._unit_of_measurement = ENERGY_KILO_WATT_HOUR
            self._unit_prefix = "k"
        self._source = f"sensor.{slugify(device.name)}_power"

        super().__init__(
            self._source,
            self._attr_name,
            2,
            self._unit_prefix,
            "h",
            self._unit_of_measurement,
            TRAPEZOIDAL_METHOD,
        )
        self._state = 0
        self._last_period = 0
        LOG.debug(
            f"Setting up EnergySensor entity: {self._attr_name} with source {self._source}"
        )

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        LOG.debug(f"Added to hass: {self._attr_name}")
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._state = state.state


class HiloCostSensor(RestoreEntity):
    def __init__(self, name, plan_name, amount=0):
        self.data = None
        self._name = name
        self.plan_name = plan_name
        self._amount = amount
        self._last_update = dt_util.utcnow()
        LOG.info(f"Initializing energy cost sensor {name} {plan_name} ")

    @property
    def name(self):
        return self._name

    @property
    def icon(self):
        return "mdi:cash"

    @property
    def state(self):
        return self._amount

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state_class(self):
        return STATE_CLASS_MEASUREMENT

    @property
    def device_class(self):
        return "monetary"

    @property
    def unit_of_measurement(self):
        return "$/kWh"

    @property
    def extra_state_attributes(self):
        return {"last_update": self._last_update, "Cost": self.state}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_update = dt_util.utcnow()
            self._amount = last_state.state

    async def async_update(self):
        return
