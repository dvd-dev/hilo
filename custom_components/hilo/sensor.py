"""Support for various Hilo sensors."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.integration.sensor import METHOD_LEFT, IntegrationSensor
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_SCAN_INTERVAL,
    CURRENCY_DOLLAR,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_MONETARY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    ENERGY_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    SOUND_PRESSURE_DB,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, slugify
import homeassistant.util.dt as dt_util
from pyhilo.device import HiloDevice
from pyhilo.event import Event
from pyhilo.util import from_utc_timestamp

from . import Hilo, HiloEntity
from .const import (
    CONF_ENERGY_METER_PERIOD,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_TARIFF,
    CONF_UNTARIFICATED_DEVICES,
    DEFAULT_ENERGY_METER_PERIOD,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_UNTARIFICATED_DEVICES,
    DOMAIN,
    EVENT_SCAN_INTERVAL,
    HILO_ENERGY_TOTAL,
    HILO_SENSOR_CLASSES,
    LOG,
    REWARD_SCAN_INTERVAL,
    TARIFF_LIST,
)
from .managers import EnergyManager, UtilityManager

WIFI_STRENGTH = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Full": 4,
}


# From netatmo integration
def process_wifi(strength: int) -> str:
    """Process wifi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


def validate_tariff_list(tariff_config):
    tariff_list = TARIFF_LIST
    for tariff in TARIFF_LIST:
        if not tariff_config.get(tariff, 0):
            tariff_list.remove(tariff)
    return tariff_list


def generate_entities_from_device(device, hilo, scan_interval):
    entities = []
    if device.type == "Gateway":
        entities.append(
            HiloChallengeSensor(hilo, device, scan_interval),
        )
        entities.append(
            HiloRewardSensor(hilo, device, scan_interval),
        )
        entities.append(
            HiloNotificationSensor(hilo, device, scan_interval),
        )
    if device.has_attribute("current_temperature"):
        entities.append(TemperatureSensor(hilo, device))
    if device.has_attribute("co2"):
        entities.append(Co2Sensor(hilo, device))
    if device.has_attribute("noise"):
        entities.append(NoiseSensor(hilo, device))
    if device.has_attribute("wifi_status"):
        entities.append(WifiStrengthSensor(hilo, device))
    if device.has_attribute("battery"):
        entities.append(BatterySensor(hilo, device))
    if device.type in HILO_SENSOR_CLASSES:
        entities.append(DeviceSensor(hilo, device))
    if device.has_attribute("power"):
        entities.append(PowerSensor(hilo, device))
    return entities


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hilo sensors based on a config entry."""
    hilo = hass.data[DOMAIN][entry.entry_id]
    new_entities = []
    cost_entities = []
    hq_plan_name = entry.options.get(CONF_HQ_PLAN_NAME, DEFAULT_HQ_PLAN_NAME)
    untarificated_devices = entry.options.get(
        CONF_UNTARIFICATED_DEVICES, DEFAULT_UNTARIFICATED_DEVICES
    )
    energy_meter_period = entry.options.get(
        CONF_ENERGY_METER_PERIOD, DEFAULT_ENERGY_METER_PERIOD
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    generate_energy_meters = entry.options.get(
        CONF_GENERATE_ENERGY_METERS, DEFAULT_GENERATE_ENERGY_METERS
    )
    tariff_config = CONF_TARIFF.get(hq_plan_name)
    if untarificated_devices:
        default_tariff_list = ["total"]
    else:
        default_tariff_list = validate_tariff_list(tariff_config)
    if generate_energy_meters:
        energy_manager = await EnergyManager().init(hass, energy_meter_period)
        utility_manager = UtilityManager(hass, energy_meter_period)

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
        tariff_list = default_tariff_list
        if device.type == "Meter":
            energy_entity = HILO_ENERGY_TOTAL
            tariff_list = validate_tariff_list(tariff_config)
        net_consumption = device.net_consumption
        utility_manager.add_meter(energy_entity, tariff_list, net_consumption)
        energy_manager.add_to_dashboard(energy_entity, tariff_list)

    for d in hilo.devices.all:
        LOG.debug(f"Adding device {d}")
        new_entities.extend(generate_entities_from_device(d, hilo, scan_interval))
        if d.has_attribute("power"):
            # If we opt out the geneneration of meters we just create the power sensors
            if generate_energy_meters:
                create_energy_entity(d)

    async_add_entities(new_entities)
    if not generate_energy_meters:
        return
    # Creating cost sensors based on plan
    # This will generate hilo_cost_(low|medium|high) sensors which can be
    # referred later in the energy dashboard based on the tarif selected
    for tarif, amount in tariff_config.items():
        if amount > 0:
            sensor_name = f"hilo_rate_{tarif}"
            cost_entities.append(HiloCostSensor(sensor_name, hq_plan_name, amount))
    cost_entities.append(HiloCostSensor("hilo_rate_current", hq_plan_name))
    async_add_entities(cost_entities)
    # This setups the utility_meter platform
    await utility_manager.update(async_add_entities)
    # This sends the entities to the energy dashboard
    await energy_manager.update()


class BatterySensor(HiloEntity, SensorEntity):
    """Define a Battery sensor entity."""

    _attr_device_class = DEVICE_CLASS_BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Battery"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-battery"
        LOG.debug(f"Setting up BatterySensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(int(self._device.get_value("battery", 0)))

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        level = round(int(self._device.get_value("battery", 0)) / 10) * 10
        if level < 10:
            return "mdi:battery-alert"
        return f"mdi:battery-{level}"


class Co2Sensor(HiloEntity, SensorEntity):
    """Define a Co2 sensor entity."""

    _attr_device_class = DEVICE_CLASS_CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} WifiStrength"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-co2"
        LOG.debug(f"Setting up WifiStrengthSensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(int(self._device.get_value("co2", 0)))

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        return "mdi:molecule-co2"


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
            integration_method=METHOD_LEFT,
            name=self._attr_name,
            round_digits=2,
            source_entity=self._source,
            unique_id=self._attr_unique_id,
            unit_prefix=self._unit_prefix,
            unit_time="h",
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


class NoiseSensor(HiloEntity, SensorEntity):
    """Define a Netatmo noise sensor entity."""

    _attr_device_class = None
    _attr_native_unit_of_measurement = SOUND_PRESSURE_DB
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Noise"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-noise"
        LOG.debug(f"Setting up NoiseSensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(int(self._device.get_value("noise", 0)))

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        if int(self._device.get_value("noise", 0)) > 0:
            return "mdi:volume-vibrate"
        return "mdi:volume-mute"


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

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        power = int(self._device.get_value("power", 0))
        if power > 0:
            return "mdi:power-plug"
        return "mdi:power-plug-off"


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
        return str(float(self._device.get_value("current_temperature", 0)))

    @property
    def icon(self):
        current_temperature = int(self._device.get_value("current_temperature", 0))
        if not self._device.available:
            thermometer = "off"
        elif current_temperature >= 22:
            thermometer = "high"
        elif current_temperature >= 18:
            thermometer = "low"
        else:
            thermometer = "alert"
        return f"mdi:thermometer-{thermometer}"


class WifiStrengthSensor(HiloEntity, SensorEntity):
    """Define a Wifi strength sensor entity."""

    _attr_device_class = DEVICE_CLASS_SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} WifiStrength"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-wifistrength"
        LOG.debug(f"Setting up WifiStrengthSensor entity: {self._attr_name}")

    @property
    def state(self):
        return process_wifi(self._device.get_value("wifi_status", 0))

    @property
    def icon(self):
        if not self._device.available or self._device.get_value("wifi_status", 0) == 0:
            return "mdi:wifi-strength-off"
        return f"mdi:wifi-strength-{WIFI_STRENGTH[self.state]}"

    @property
    def extra_state_attributes(self):
        return {"wifi_signal": self._device.get_value("wifi_status", 0)}


class HiloNotificationSensor(HiloEntity, RestoreEntity, SensorEntity):
    """Hilo Notification sensor.
    Its state will be the number of notification waiting in the Hilo app.
    """

    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Notifications Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = slugify(self._attr_name)
        LOG.debug(f"Setting up NotificationSensor entity: {self._attr_name}")
        self.scan_interval = timedelta(seconds=scan_interval)
        self._state = 0
        self._notifications = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        try:
            return int(self._state)
        except ValueError:
            return 0

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state > 0:
            return "mdi:bell-alert"
        return "mdi:bell-outline"

    @property
    def should_poll(self):
        return True

    @property
    def extra_state_attributes(self):
        return {"notifications": self._notifications}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_update = dt_util.utcnow()
            self._state = last_state.state

    async def _async_update(self):
        self._notifications = []
        for notification in await self._hilo._api.get_event_notifications(
            self._hilo.devices.location_id
        ):
            if notification.get("viewed"):
                continue
            self._notifications.append(
                {
                    "type_id": notification.get("eventTypeId"),
                    "event_id": notification.get("eventId"),
                    "device_id": notification.get("deviceId"),
                    "date": from_utc_timestamp(notification.get("notificationDateUTC")),
                    "title": notification.get("notificationTitle"),
                    "body": notification.get("notificationBody"),
                }
            )
        self._state = len(self._notifications)


class HiloRewardSensor(HiloEntity, RestoreEntity, SensorEntity):
    """Hilo Reward sensor.
    Its state will be either the total amount rewarded this season.
    """

    _attr_device_class = DEVICE_CLASS_MONETARY
    _attr_state_class = STATE_CLASS_TOTAL_INCREASING

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Recompenses Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = slugify(self._attr_name)
        LOG.debug(f"Setting up RewardSensor entity: {self._attr_name}")
        self.scan_interval = timedelta(seconds=REWARD_SCAN_INTERVAL)
        self._attr_native_unit_of_measurement = hilo._hass.config.currency
        self._state = 0
        self._history = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        return "mdi:cash-plus"

    @property
    def should_poll(self):
        return True

    @property
    def extra_state_attributes(self):
        return {"history": self._history}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_update = dt_util.utcnow()
            self._state = last_state.state

    async def _async_update(self):
        seasons = await self._hilo._api.get_seasons(self._hilo.devices.location_id)
        if seasons:
            new_history = []
            for idx, season in enumerate(seasons):
                if idx == 0:
                    self._state = season.get("totalReward", 0)
                events = []
                for raw_event in season.get("events", []):
                    details = await self._hilo._api.get_gd_events(
                        self._hilo.devices.location_id, event_id=raw_event["id"]
                    )
                    events.append(Event(**details).as_dict())
                season["events"] = events
                new_history.append(season)
            self._history = new_history


class HiloChallengeSensor(HiloEntity, RestoreEntity, SensorEntity):
    """Hilo challenge sensor.
    Its state will be either:
    - off: no ongoing or scheduled challenge
    - scheduled: A challenge is scheduled, details in the next_events
                 extra attribute
    - pre_heat: Currently in the pre-heat phase
    - reduction or on: Challenge is currently active, heat is lowered
    - recovery: Challenge is completed, we're reheating.
    """

    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Defi Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = slugify(self._attr_name)
        LOG.debug(f"Setting up ChallengeSensor entity: {self._attr_name}")
        self.scan_interval = timedelta(seconds=EVENT_SCAN_INTERVAL)
        self._state = "off"
        self._next_events = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state == "appreciation":
            return "mdi:glass-cocktail"
        if self.state == "off":
            return "mdi:lightning-bolt"
        if self.state == "scheduled":
            return "mdi:progress-clock"
        if self.state == "pre_heat":
            return "mdi:radiator"
        if self.state in ["reduction", "on"]:
            return "mdi:power-plug-off"
        if self.state == "recovery":
            return "mdi:calendar-check"
        return "mdi:battery-alert"

    @property
    def should_poll(self):
        return True

    @property
    def extra_state_attributes(self):
        return {"next_events": self._next_events}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_update = dt_util.utcnow()
            self._state = last_state.state
            self._next_events = last_state.attributes.get("next_events", [])

    async def _async_update(self):
        new_events = []
        events = await self._hilo._api.get_gd_events(self._hilo.devices.location_id)
        LOG.debug(f"Events received from Hilo: {events}")
        for raw_event in events:
            details = await self._hilo._api.get_gd_events(
                self._hilo.devices.location_id, event_id=raw_event["id"]
            )
            event = Event(**details)
            if self._hilo.appreciation > 0:
                event.appreciation(self._hilo.appreciation)
            new_events.append(event.as_dict())
        self._state = "off"
        self._next_events = []
        if len(new_events):
            self._state = new_events[0]["state"]
            self._next_events = new_events


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
    def extra_state_attributes(self):
        return {k: self._device.get_value(k) for k in self._device.attributes}

    @property
    def icon(self):
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state == "off":
            return "mdi:access-point-network-off"
        return "mdi:access-point-network"


class HiloCostSensor(RestoreEntity, SensorEntity):

    _attr_device_class = DEVICE_CLASS_MONETARY
    _attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/{ENERGY_KILO_WATT_HOUR}"
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_icon = "mdi:cash"

    def __init__(self, name, plan_name, amount=0):
        self.data = None
        self._attr_name = name
        self.plan_name = plan_name
        self._amount = amount
        self._last_update = dt_util.utcnow()
        LOG.info(f"Initializing energy cost sensor {name} {plan_name} Amount: {amount}")

    @property
    def state(self):
        return self._amount

    @property
    def should_poll(self) -> bool:
        return False

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
