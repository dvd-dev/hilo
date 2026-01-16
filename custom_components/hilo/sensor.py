"""Support for various Hilo sensors."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from os.path import isfile

import aiofiles
from homeassistant.components.integration.sensor import METHOD_LEFT, IntegrationSensor
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_SCAN_INTERVAL,
    CURRENCY_DOLLAR,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    STATE_UNKNOWN,
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfSoundPressure,
    UnitOfTemperature,
    __short_version__ as current_version,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, slugify
import homeassistant.util.dt as dt_util
from packaging.version import Version
from pyhilo.const import UNMONITORED_DEVICES
from pyhilo.device import HiloDevice
from pyhilo.event import Event
from pyhilo.util import from_utc_timestamp
import yaml
from yaml.scanner import ScannerError

from . import Hilo
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
    EVENT_SCAN_INTERVAL_REDUCTION,
    HILO_ENERGY_TOTAL,
    HILO_SENSOR_CLASSES,
    LOG,
    MAX_SUB_INTERVAL,
    MIN_SCAN_INTERVAL,
    NOTIFICATION_SCAN_INTERVAL,
    REWARD_SCAN_INTERVAL,
    TARIFF_LIST,
    WEATHER_CONDITIONS,
)
from .entity import HiloEntity
from .managers import EnergyManager, UtilityManager

WIFI_STRENGTH = {
    "Low": 1,
    "Medium": 2,
    "High": 3,
    "Full": 4,
}


# From netatmo integration
def process_wifi(strength: int) -> str:
    """Process Wi-Fi signal strength and return string for display."""
    if strength >= 86:
        return "Low"
    if strength >= 71:
        return "Medium"
    if strength >= 56:
        return "High"
    return "Full"


def validate_tariff_list(tariff_config):
    """Validate the tariff list from the configuration."""
    return TARIFF_LIST


def generate_entities_from_device(device, hilo, scan_interval):
    """Generate the entities from the device description."""
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
        entities.append(
            HiloOutdoorTempSensor(hilo, device, scan_interval),
        )
    if device.has_attribute("battery"):
        entities.append(BatterySensor(hilo, device))
    if device.has_attribute("co2"):
        entities.append(Co2Sensor(hilo, device))
    if device.has_attribute("current_temperature"):
        entities.append(TemperatureSensor(hilo, device))
    if device.type in HILO_SENSOR_CLASSES:
        entities.append(DeviceSensor(hilo, device))
    if device.has_attribute("noise"):
        entities.append(NoiseSensor(hilo, device))
    if device.has_attribute("power") and device.model not in UNMONITORED_DEVICES:
        entities.append(PowerSensor(hilo, device))
    if device.has_attribute("target_temperature"):
        entities.append(TargetTemperatureSensor(hilo, device))
    if device.has_attribute("wifi_status"):
        entities.append(WifiStrengthSensor(hilo, device))
    return entities


# noinspection GrazieInspection
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
        utility_manager = UtilityManager(hass, energy_meter_period, default_tariff_list)

    def create_energy_entity(hilo, device):
        device._energy_entity = EnergySensor(hilo, device, hass)
        new_entities.append(device._energy_entity)
        energy_entity = f"{slugify(device.name)}_hilo_energy"
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

    for d in hilo.devices.all:
        LOG.debug("Adding device %s", d)
        new_entities.extend(generate_entities_from_device(d, hilo, scan_interval))
        if d.has_attribute("power") and d.model not in UNMONITORED_DEVICES:
            # If we opt out the generation of meters we just create the power sensors
            if generate_energy_meters:
                create_energy_entity(hilo, d)

    async_add_entities(new_entities)
    if not generate_energy_meters:
        return
    # Creating cost sensors based on plan
    # This will generate hilo_cost_(low|medium|high) sensors which can be
    # referred later in the energy dashboard based on the tarif selected
    hilo.cost_sensors = {}
    for tarif, amount in tariff_config.items():
        if amount > 0:
            sensor_name = f"Hilo rate {tarif}"
            sensor = HiloCostSensor(hilo, sensor_name, hq_plan_name, amount)
            cost_entities.append(sensor)
            hilo.cost_sensors[tarif] = sensor  # Stores reference for check_tarif

    hilo_rate_current = HiloCostSensor(hilo, "Hilo rate current", hq_plan_name)
    cost_entities.append(hilo_rate_current)

    # Create hilo_rate_current_total sensor that includes access rate per hour
    access_rate = tariff_config.get("access", 0)
    hilo_rate_current_total = HiloCostSensorTotal(
        hilo, "Hilo rate current total", hq_plan_name, access_rate
    )
    cost_entities.append(hilo_rate_current_total)

    async_add_entities(cost_entities)
    async_track_state_change_event(
        hilo._hass, ["sensor.hilo_rate_current"], hilo_rate_current._handle_state_change
    )
    async_track_state_change_event(
        hilo._hass,
        ["sensor.hilo_rate_current"],
        hilo_rate_current_total._handle_state_change,
    )
    # This setups the utility_meter platform
    await utility_manager.update(async_add_entities)
    # This sends the entities to the energy dashboard
    await energy_manager.update()


class BatterySensor(HiloEntity, SensorEntity):
    """Define a Battery sensor entity."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo battery sensor initialization."""
        self._attr_name = f"{device.name} Battery"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-battery"
        self._attr_unique_id = f"{slugify(device.identifier)}-battery"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up BatterySensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the battery level."""
        return str(int(self._device.get_value("battery", 0)))

    @property
    def icon(self):
        """Return the icon representing the battery level."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        level = round(int(self._device.get_value("battery", 0)) / 10) * 10
        if level < 10:
            return "mdi:battery-alert"
        return f"mdi:battery-{level}"


class Co2Sensor(HiloEntity, SensorEntity):
    """Define a Co2 sensor entity."""

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo CO2 sensor initialization."""
        self._attr_name = f"{device.name} CO2"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-co2"
        self._attr_unique_id = f"{slugify(device.identifier)}-co2"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up CO2Sensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the CO2 level."""
        return str(int(self._device.get_value("co2", 0)))

    @property
    def icon(self):
        """Return the icon representing the CO2 level."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        return "mdi:molecule-co2"


class EnergySensor(IntegrationSensor):
    """Define a Hilo energy sensor entity."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, hilo, device, hass):
        """Hilo Energy sensor initialization."""
        self._device = device
        self._attr_name = f"{device.name} Hilo Energy"
        old_unique_id = f"hilo_energy_{slugify(device.name)}"
        self._attr_unique_id = f"{slugify(device.identifier)}-energy"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._suggested_display_precision = 2

        if device.type == "Meter":
            self._attr_name = HILO_ENERGY_TOTAL
        self._source = f"sensor.{slugify(device.name)}_power"
        # ic-dev21: Set initial state and last_valid_state, removes log errors and unavailable states
        initial_state = 0
        self._attr_native_value = initial_state
        self._attr_last_valid_state = initial_state
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device.identifier)},
        )

        if Version(current_version) >= Version("2025.8"):
            super().__init__(
                hass,
                integration_method=METHOD_LEFT,
                max_sub_interval=timedelta(seconds=MAX_SUB_INTERVAL),
                name=self._attr_name,
                round_digits=2,
                source_entity=self._source,
                unique_id=self._attr_unique_id,
                unit_prefix="k",
                unit_time="h",
            )
        elif Version(current_version) >= Version("2024.7"):
            super().__init__(
                integration_method=METHOD_LEFT,
                max_sub_interval=timedelta(seconds=MAX_SUB_INTERVAL),
                name=self._attr_name,
                round_digits=2,
                source_entity=self._source,
                unique_id=self._attr_unique_id,
                unit_prefix="k",
                unit_time="h",
                device_info=self._device_info,
            )
        else:
            super().__init__(
                integration_method=METHOD_LEFT,
                name=self._attr_name,
                round_digits=2,
                source_entity=self._source,
                unique_id=self._attr_unique_id,
                unit_prefix="k",
                unit_time="h",
                device_info=self._device_info,
            )
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._suggested_display_precision = 2

        self._attr_icon = "mdi:lightning-bolt"
        LOG.debug(
            "Setting up EnergySensor entity: %s with source %s",
            self._attr_name,
            self._source,
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._attr_unit_of_measurement

    @property
    def suggested_display_precision(self):
        """Return the suggested display precision."""
        return self._attr_suggested_display_precision

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        LOG.debug("Added to hass: %s", self._attr_name)
        await super().async_added_to_hass()


class NoiseSensor(HiloEntity, SensorEntity):
    """Define a Netatmo noise sensor entity."""

    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo Noise sensor initialization."""
        self._attr_name = f"{device.name} Noise"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-noise"
        self._attr_unique_id = f"{slugify(device.identifier)}-noise"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up NoiseSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the current noise level."""
        return str(int(self._device.get_value("noise", 0)))

    @property
    def icon(self):
        """Return the icon representing the noise level."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        if int(self._device.get_value("noise", 0)) > 0:
            return "mdi:volume-vibrate"
        return "mdi:volume-mute"


class PowerSensor(HiloEntity, SensorEntity):
    """Define a Hilo power sensor entity."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo: Hilo, device: HiloDevice) -> None:
        """Initialize."""
        self._attr_name = f"{device.name} Power"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-power"
        self._attr_unique_id = f"{slugify(device.identifier)}-power"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up PowerSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the current power state."""
        return str(int(self._device.get_value("power", 0)))

    @property
    def icon(self):
        """Return the icon representing the power state."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        power = int(self._device.get_value("power", 0))
        if power > 0:
            return "mdi:power-plug"
        return "mdi:power-plug-off"


class TemperatureSensor(HiloEntity, SensorEntity):
    """Define a Hilo temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo Temperature sensor initialization."""
        self._attr_name = f"{device.name} Temperature"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-temperature"
        self._attr_unique_id = f"{slugify(device.identifier)}-temperature"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up TemperatureSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the current temperature."""
        return str(float(self._device.get_value("current_temperature", 0)))

    @property
    def icon(self):
        """Return the icon representing the current temperature."""
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


class TargetTemperatureSensor(HiloEntity, SensorEntity):
    """Define a Hilo target temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo Target Temperature sensor initialization."""
        self._attr_name = f"{device.name} Target Temperature"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-target-temperature"
        self._attr_unique_id = f"{slugify(device.identifier)}-target-temperature"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up TargetTemperatureSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the target temperature."""
        return str(float(self._device.get_value("target_temperature", 0)))

    @property
    def icon(self):
        """Return the icon representing the target temperature."""
        target_temperature = int(self._device.get_value("target_temperature", 0))
        if not self._device.available:
            thermometer = "off"
        elif target_temperature >= 22:
            thermometer = "high"
        elif target_temperature >= 18:
            thermometer = "low"
        else:
            thermometer = "alert"
        return f"mdi:thermometer-{thermometer}"


class WifiStrengthSensor(HiloEntity, SensorEntity):
    """Define a Wi-Fi strength sensor entity."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        """Hilo Wi-Fi strength sensor initialization."""
        self._attr_name = f"{device.name} WifiStrength"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = f"{slugify(device.name)}-wifistrength"
        LOG.debug("Setting up WifiStrengthSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the Wi-Fi signal strength."""
        return process_wifi(self._device.get_value("wifi_status", 0))

    @property
    def icon(self):
        """Return the icon representing the Wi-Fi strength."""
        if not self._device.available or self._device.get_value("wifi_status", 0) == 0:
            return "mdi:wifi-strength-off"
        return f"mdi:wifi-strength-{WIFI_STRENGTH[self.state]}"

    @property
    def extra_state_attributes(self):
        """Return the Wi-Fi signal strength."""
        return {"wifi_signal": self._device.get_value("wifi_status", 0)}


class HiloNotificationSensor(HiloEntity, RestoreEntity, SensorEntity):
    """Hilo Notification sensor.

    Its state will be the number of notification waiting in the Hilo app.
    Notifications only used for OneLink's alerts & Low-battery warnings.
    We should consider having this sensor enabled only if a smoke detector is in use.
    """

    def __init__(self, hilo, device, scan_interval):
        """Hilo Notification sensor initialization."""
        self._attr_name = "Notifications Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up NotificationSensor entity: %s", self._attr_name)
        self.scan_interval = timedelta(seconds=NOTIFICATION_SCAN_INTERVAL)
        self._state = 0
        self._notifications = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        """Return the number of notifications."""
        try:
            return int(self._state)
        except ValueError:
            return 0

    @property
    def icon(self):
        """Return the icon based on the notification state."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state > 0:
            return "mdi:bell-alert"
        return "mdi:bell-outline"

    @property
    def should_poll(self):
        """Enable polling."""
        return True

    @property
    def extra_state_attributes(self):
        """Return the notifications."""
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

    Its state will be either 0 or the total amount rewarded this season.
    """

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _entity_component_unrecorded_attributes = frozenset({"history"})

    def __init__(self, hilo, device, scan_interval):
        """Hilo Reward sensor initialization."""
        self._attr_name = "Recompenses Hilo"

        # Check if currency is configured, set a default if not
        currency = hilo._hass.config.currency
        if currency:
            self._attr_native_unit_of_measurement = currency
        else:
            self._attr_native_unit_of_measurement = "CAD"

        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up RewardSensor entity: %s", self._attr_name)
        self._history_state_yaml: str = "hilo_eventhistory_state.yaml"
        self.scan_interval = timedelta(seconds=REWARD_SCAN_INTERVAL)
        self._state = 0
        self._history = []
        self._events_to_poll = dict()
        self.async_update = Throttle(self.scan_interval)(self._async_update)
        hilo.register_websocket_listener(self)

        # When we update the list of reward history, we can end up making
        # hundreds of calls to _save_history in a very short amount of time.
        # With a debouncer, we can reduce this to a single save, which is more
        # efficient (save can become pretty slow when the history is long) and
        # makes sure Home Assistant is not slowed down. Some websocket could
        # even lose connection due to the delay introduced by saving many times.
        LOG.debug("Setting up debouncer for history saver")
        self._save_history_debouncer = Debouncer(
            hilo._hass,
            LOG,
            cooldown=5,  # Wait for 5 seconds before writing to file
            immediate=False,
            function=self._save_history,
        )

    @property
    def state(self):
        """Return the total reward amount for the current season."""
        return self._state

    @property
    def icon(self):
        """Set the icon based on the current state."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        return "mdi:cash-plus"

    @property
    def should_poll(self):
        """Enable polling."""
        return True

    @property
    def extra_state_attributes(self):
        """Return the history attributes."""
        return {"history": self._history}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self._last_update = dt_util.utcnow()
            self._state = last_state.state

    async def handle_challenge_details_update(self, challenge):
        """Handle challenge details update from websocket."""
        LOG.debug("UPDATING challenge in reward: %s", challenge)

        # We're getting events but didn't request any, do not process them
        if len(self._events_to_poll.items()) == 0:
            return

        # Only process events that contain an id and phases
        if challenge.get("id") is None or challenge.get("phases") is None:
            return

        # Skip messages about upcoming events since they don't contain useful info about rewards
        if challenge.get("report")["status"] == "Upcoming":
            LOG.debug(
                "Skipping upcoming challenge event in reward: %s", challenge.get("id")
            )
            return

        event = Event(**challenge).as_dict()
        corresponding_season = self._events_to_poll[event["event_id"]]
        del self._events_to_poll[event["event_id"]]

        for season in self._history:
            if season.get("season") == corresponding_season:
                for i, season_event in enumerate(season["events"]):
                    if season_event["event_id"] == event["event_id"]:
                        LOG.debug(
                            "ChallengeId matched, replacing: %s", event["event_id"]
                        )

                        # Some events from the websocket don't contain reward info. Copying it from history (API) if it's there
                        event["reward"] = season_event.get("reward", 0.0)
                        season["events"][i] = event  # On update
                        season["events"] = [
                            item
                            for item in sorted(
                                season["events"], key=lambda x: int(x["event_id"])
                            )
                        ]
                        await self._save_history_debouncer.async_call()
                        return
                LOG.debug("ChallengeId did not match, appending: %s", event["event_id"])
                season["events"].append(event)
                season["events"] = [
                    item
                    for item in sorted(
                        season["events"], key=lambda x: int(x["event_id"])
                    )
                ]

        await self._save_history_debouncer.async_call()

    async def _async_update(self):
        seasons = await self._hilo._api.get_seasons(self._hilo.devices.location_id)
        self._events_to_poll = dict()
        seasons = sorted(seasons, key=lambda x: x["season"], reverse=True)

        # Re-add the totalReward that was present in the legacy API
        for season_data in seasons:
            total = sum(
                event["reward"]
                for event in season_data["events"]
                if "reward" in event and not event.get("isPreseasonEvent")
            )
            season_data["totalReward"] = total

        if seasons:
            current_history = await self._load_history()
            new_history = []

            for idx, season in enumerate(seasons):
                current_history_season = next(
                    (
                        item
                        for item in current_history
                        if item.get("season") == season.get("season")
                    ),
                    None,
                )

                if idx == 0:
                    self._state = season.get("totalReward", 0)
                events = []
                for raw_event in season.get("events", []):
                    current_history_event = None
                    event = None

                    if current_history_season:
                        current_history_event = next(
                            (
                                ev
                                for ev in current_history_season["events"]
                                if ev["event_id"] == raw_event["id"]
                            ),
                            None,
                        )

                    start_date_utc = datetime.fromisoformat(raw_event["startDateUtc"])
                    event_age = datetime.now(timezone.utc) - start_date_utc
                    if (
                        current_history_event
                        and current_history_event.get("state") == "off"
                        and event_age > timedelta(days=1)
                    ):
                        # No point updating events for previously completed events, they won't change.
                        event = current_history_event
                    else:
                        # Save the event to poll in a dict so that we can easily lookup the season when the websocket event comes in
                        self._events_to_poll[raw_event["id"]] = season.get("season")
                        event = Event(**raw_event).as_dict()

                        # details = await self._hilo.get_event_details(raw_event["id"])
                        # event = Event(**details).as_dict()

                    if event:
                        events.append(event)

                season["events"] = events
                new_history.append(season)

            self._history = new_history
            await self._save_history_debouncer.async_call()
            for eventId in self._events_to_poll:
                await self._hilo.subscribe_to_challenge(1, eventId)

    async def _load_history(self) -> list:
        history: list = []
        if isfile(self._history_state_yaml):
            async with aiofiles.open(self._history_state_yaml, mode="r") as yaml_file:
                LOG.debug("Loading history state from yaml")
                content = await yaml_file.read()
                try:
                    history = yaml.load(content, Loader=yaml.Loader)
                except ScannerError:
                    LOG.error("History state YAML is corrupted, resetting to default.")
                if not history or not isinstance(history, list):
                    LOG.error("History state YAML is invalid, resetting to default.")
                    history = []

        return history

    async def _save_history(self):
        async with aiofiles.open(self._history_state_yaml, mode="w") as yaml_file:
            LOG.debug("Saving history state to yaml file")
            # TODO: Use asyncio.get_running_loop() and run_in_executor to write
            # to the file in a non blocking manner. Currently, the file writes
            # are properly async but the yaml dump is done synchroniously on the
            # main event loop
            await yaml_file.write(yaml.dump(self._history))


class HiloChallengeSensor(HiloEntity, SensorEntity):
    """Hilo challenge sensor.

    Its state will be either:
    - off: no ongoing or scheduled challenge
    - scheduled: A challenge is scheduled, details in the next_events
                 extra attribute
    - pre_cold: optional phase to cool further before appreciation
    - appreciation: optional phase to pre-heat more before challenge
    - pre_heat: Currently in the pre-heat phase
    - reduction or on: Challenge is currently active, heat is lowered
    - recovery: Challenge is completed, we're reheating.
    """

    def __init__(self, hilo, device, scan_interval):
        """Hilo Challenge sensor initialization."""
        self._attr_name = "Defi Hilo"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = [
            "off",
            "scheduled",
            "pre_cold",
            "appreciation",
            "pre_heat",
            "reduction",
            "recovery",
            "completed",
            "unknown",
        ]
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up ChallengeSensor entity: %s", self._attr_name)
        self.scan_interval = timedelta(seconds=EVENT_SCAN_INTERVAL_REDUCTION)
        self._state = "off"
        self._next_events = []
        self._events = {}  # Store active events
        self.async_update = Throttle(timedelta(seconds=MIN_SCAN_INTERVAL))(
            self._async_update
        )
        hilo.register_websocket_listener(self)

    async def handle_challenge_added(self, event_data):
        """Handle new challenge event."""
        LOG.debug("handle_challenge_added running")
        if event_data.get("progress") == "scheduled":
            event_id = event_data.get("id")
            if event_id:
                event = Event(**event_data)
                if self._hilo.appreciation > 0:
                    event.appreciation(self._hilo.appreciation)
                if self._hilo.pre_cold > 0:
                    event.pre_cold(self._hilo.pre_cold)
                self._events[event_id] = event
                self._update_next_events()

    async def handle_challenge_list_initial(self, challenges):
        """Handle initial challenge list."""
        LOG.debug("handle_challenge_list_initial challenges: %s", challenges)
        self._events.clear()
        LOG.debug("handle_challenge_list_initial events: %s", self._events)
        for challenge in challenges:
            event_id = challenge.get("id")
            progress = challenge.get("progress")
            LOG.debug("handle_challenge_list_initial progress is %s", progress)
            if challenge.get("progress") in ["scheduled", "inProgress"]:
                event_id = challenge.get("id")
                if event_id:
                    event = Event(**challenge)
                    if self._hilo.appreciation > 0:
                        event.appreciation(self._hilo.appreciation)
                    if self._hilo.pre_cold > 0:
                        event.pre_cold(self._hilo.pre_cold)
                    self._events[event_id] = event
        self._update_next_events()

    async def handle_challenge_list_update(self, challenges):
        """Handle challenge list updates."""
        LOG.debug("handle_challenge_list_update is running")
        for challenge in challenges:
            event_id = challenge.get("id")
            progress = challenge.get("progress")
            baselinewH = challenge.get("baselineWh")
            LOG.debug("handle_challenge_list_update progress is %s", progress)
            LOG.debug("handle_challenge_list_update baselineWh is %s", baselinewH)
            if event_id in self._events:
                if challenge.get("progress") == "completed":
                    # Find the oldest event based on recovery_end datetime
                    oldest_event_id = min(
                        self._events.keys(),
                        key=lambda key: self._events[key]
                        .as_dict()
                        .get("phases", {})
                        .get("recovery_end", ""),
                    )
                    await asyncio.sleep(300)
                    del self._events[oldest_event_id]
                    break
                else:
                    current_event = self._events[event_id]
                    LOG.debug(
                        "handle_challenge_list_update current event is: %s",
                        current_event,
                    )
                    updated_event = Event(**{**current_event.as_dict(), **challenge})
                    if self._hilo.appreciation > 0:
                        updated_event.appreciation(self._hilo.appreciation)
                    if self._hilo.pre_cold > 0:
                        updated_event.pre_cold(self._hilo.pre_cold)
                    self._events[event_id] = updated_event
        self._update_next_events()

    async def handle_challenge_details_update(self, challenge):
        """Handle challenge detail updates."""
        LOG.debug("handle_challenge_details_update challenge is %s", challenge)
        challenge = challenge[0] if isinstance(challenge, list) else challenge
        event_id = challenge.get("id")
        event_has_id = event_id is not None

        # In case we get a consumption update (there is no event id),
        # get the event id of the next event so that we can update it
        if event_id is None and len(self._next_events) > 0:
            event_id = self._next_events[0]["event_id"]

        progress = challenge.get("progress", "unknown")

        baseline_points = challenge.get("cumulativeBaselinePoints", [])

        if not baseline_points:
            consumption = challenge.get("consumption", {})
            baseline_points = consumption.get("cumulativeBaselinePoints", [])
        if baseline_points:
            baselinewH = baseline_points[-1]["wh"]
        else:
            baselinewH = challenge.get("baselineWh", 0)
        allowed_kwh = baselinewH / 1000 if baselinewH > 0 else 0

        used_wH = challenge.get("currentWh", 0)
        if used_wH is not None and used_wH > 0:
            used_kWh = used_wH / 1000
        else:
            used_kWh = 0

        LOG.debug("handle_challenge_details_update progress is %s", progress)
        LOG.debug("handle_challenge_details_update baselineWh is %s", baselinewH)
        LOG.debug("handle_challenge_details_update used_kwh is %s", used_kWh)
        LOG.debug("handle_challenge_details_update allowed_kwh is %s", allowed_kwh)

        if event_id in self._events:
            if challenge.get("progress") == "completed":
                # ajout d'un asyncio sleep ici pour avoir l'état completed avant le retrait du challenge
                await asyncio.sleep(300)
                del self._events[event_id]

            # Consumption update
            elif used_wH is not None and used_wH > 0:
                current_event = self._events[event_id]
                current_event.update_wh(used_wH)
                if baselinewH > 0:
                    current_event.update_allowed_wh(baselinewH)
            # For non consumption updates, we need an event id
            elif event_has_id:
                current_event = self._events[event_id]
                updated_event = Event(**{**current_event.as_dict(), **challenge})
                if self._hilo.appreciation > 0:
                    updated_event.appreciation(self._hilo.appreciation)
                if self._hilo.pre_cold > 0:
                    updated_event.pre_cold(self._hilo.pre_cold)
                if baselinewH > 0:
                    updated_event.update_allowed_wh(baselinewH)
                elif current_event.allowed_kWh > 0:
                    updated_event.allowed_kWh = current_event.allowed_kWh
                self._events[event_id] = updated_event
            self._update_next_events()

    def _update_next_events(self):
        """Update the next_events list based on current events."""
        LOG.debug("_update_next_events sorting events")
        # Sort events by start time
        sorted_events = sorted(self._events.values(), key=lambda x: x.preheat_start)

        self._next_events = [event.as_dict() for event in sorted_events]

        # Force an update of the entity
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the current state based on next events."""
        if len(self._next_events) > 0:
            event = Event(**{**{"id": 0}, **self._next_events[0]})
            return event.state
        return "off"

    @property
    def icon(self):
        """Set the icon based on the current state."""
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
        if self.state == "pre_cold":
            return "mdi:radiator-off"
        return "mdi:battery-alert"

    @property
    def should_poll(self):
        """Don't poll with websockets. Poll to update allowed_wh in pre_heat phrase and consumption in reduction phase."""
        return self.state in ["recovery", "reduction", "pre_heat"]

    @property
    def extra_state_attributes(self):
        """Return the next events attribute."""
        return {"next_events": self._next_events}

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()

    async def _async_update(self):
        """Update fallback, but not needed with websockets."""
        for event_id in self._events:
            event = self._events.get(event_id)
            if event.should_check_for_allowed_wh():
                LOG.debug("ASYNC UPDATE SUB: EVENT: %s", event_id)
                await self._hilo.subscribe_to_challenge(1, event_id)
                await self._hilo.request_challenge_consumption_update(1, event_id)
            elif self.state == "reduction":
                LOG.debug("ASYNC UPDATE: EVENT: %s", event_id)
                await self._hilo.request_challenge_consumption_update(1, event_id)


class DeviceSensor(HiloEntity, SensorEntity):
    """Simple device entity.

    Devices like the gateway or Smoke Detectors don't have many attributes,
    except for the "disconnected" attribute. These entities are monitoring
    this state.
    """

    def __init__(self, hilo, device):
        """Initialize."""
        self._attr_name = device.name
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(device.name)
        self._attr_unique_id = f"{slugify(device.identifier)}-{slugify(device.name)}"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug("Setting up DeviceSensor entity: %s", self._attr_name)

    @property
    def state(self):
        """Return the connection state."""
        return "on" if self._device.available else "off"

    @property
    def extra_state_attributes(self):
        """Return the extra state attributes."""
        return {k: self._device.get_value(k) for k in self._device.attributes}

    @property
    def icon(self):
        """Set the icon based on the connection state."""
        if not self._device.available:
            return "mdi:lan-disconnect"
        if self.state == "off":
            return "mdi:access-point-network-off"
        return "mdi:access-point-network"


class HiloCostSensor(HiloEntity, SensorEntity):
    """This sensor generates cost entities."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = (
        f"{CURRENCY_DOLLAR}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash"

    def __init__(self, hilo, name, plan_name, amount=0):
        """Initialize."""
        for d in hilo.devices.all:
            if d.type == "Gateway":
                device = d
        if "low_threshold" in name:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        elif "access" in name.lower():
            # Access fee is a fixed daily cost, not per kWh
            self._attr_native_unit_of_measurement = f"{CURRENCY_DOLLAR}/day"
        self.data = None
        self._attr_name = name
        self.plan_name = plan_name
        self._last_update = dt_util.utcnow()
        self._cost = amount
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        self._last_update = dt_util.utcnow()
        super().__init__(hilo, name=self._attr_name, device=device)
        LOG.info(f"Initializing energy cost sensor {name} {plan_name} Amount: {amount}")

    def _handle_state_change(self, event):
        LOG.debug("_handle_state_change() %s | %s ", self, self._last_update)
        if (state := event.data.get("new_state")) is None:
            return

        now = dt_util.utcnow()
        try:
            if (
                state.attributes.get("hilo_update")
                and self._last_update + timedelta(seconds=30) < now
            ):
                LOG.debug(
                    "Setting new state %s state=%s state.attributes=%s",
                    state.state,
                    state,
                    state.attributes,
                )
                self._cost = state.state
                self._last_update = now
        except ValueError:
            LOG.error(f"Invalidate state received for {self._attr_unique_id}: {state}")

    @property
    def state(self):
        """Return the cost."""
        return self._cost

    @property
    def should_poll(self) -> bool:
        """Disable polling."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the cost sensor attributes."""
        return {
            "Cost": self._cost,
            "Plan": self.plan_name,
            "last_update": self._last_update,
        }

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()

    async def async_update(self):
        """Update the state."""
        self._last_update = dt_util.utcnow()


class HiloCostSensorTotal(HiloEntity, SensorEntity):
    """This sensor generates the total cost entity including access rate per hour"""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = (
        f"{CURRENCY_DOLLAR}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash"

    def __init__(self, hilo, name, plan_name, access_rate=0):
        for d in hilo.devices.all:
            if d.type == "Gateway":
                device = d
        self.data = None
        self._attr_name = name
        self.plan_name = plan_name
        self._last_update = dt_util.utcnow()
        self._current_rate = 0
        self._access_rate_per_hour = (
            access_rate / 24
        )  # Convert daily access rate to hourly
        self._total_cost = 0
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        self._last_update = dt_util.utcnow()
        super().__init__(hilo, name=self._attr_name, device=device)
        LOG.info(
            f"Initializing total energy cost sensor {name} {plan_name} "
            f"Access rate per hour: {self._access_rate_per_hour}"
        )

    def _handle_state_change(self, event):
        LOG.debug("_handle_state_change() %s | %s ", self, self._last_update)
        if (state := event.data.get("new_state")) is None:
            return

        now = dt_util.utcnow()
        try:
            if (
                state.attributes.get("hilo_update")
                and self._last_update + timedelta(seconds=30) < now
            ):
                LOG.debug(
                    "Setting new state %s state=%s state.attributes=%s",
                    state.state,
                    state,
                    state.attributes,
                )
                # Get the current rate from hilo_rate_current
                try:
                    self._current_rate = float(state.state)
                except (ValueError, TypeError):
                    self._current_rate = 0

                # Calculate total cost: current rate + access rate per hour
                self._total_cost = self._current_rate + self._access_rate_per_hour
                self._last_update = now
                self.async_write_ha_state()
        except ValueError:
            LOG.error(f"Invalid state received for {self._attr_unique_id}: {state}")

    @property
    def state(self):
        return self._total_cost

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def extra_state_attributes(self):
        return {
            "Current Rate": self._current_rate,
            "Access Rate Per Hour": self._access_rate_per_hour,
            "Total Cost": self._total_cost,
            "Plan": self.plan_name,
            "last_update": self._last_update,
        }

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()

    async def async_update(self):
        self._last_update = dt_util.utcnow()
        return super().async_update()

        return super().async_update()


class HiloOutdoorTempSensor(HiloEntity, SensorEntity):
    """Hilo outdoor temperature sensor.

    Its state will be the current outdoor weather as reported by the Hilo App
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device, scan_interval):
        """Initialize."""
        self._attr_name = "Outdoor Weather Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        LOG.debug("Setting up OutdoorWeatherSensor entity: %s", self._attr_name)
        self.scan_interval = timedelta(seconds=EVENT_SCAN_INTERVAL_REDUCTION)
        self._state = STATE_UNKNOWN
        self._weather = {}
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        """Return the current outdoor temperature."""
        try:
            return int(self._state)
        except ValueError:
            return STATE_UNKNOWN

    @property
    def icon(self):
        """Set the icon based on weather condition."""
        condition = self._weather.get("condition", "").lower()
        LOG.debug("Current condition: %s", condition)
        if not condition:
            return "mdi:lan-disconnect"
        return WEATHER_CONDITIONS.get(self._weather.get("condition", "Unknown"))

    @property
    def should_poll(self):
        """Poll needed to update weather data."""
        return True

    @property
    def extra_state_attributes(self):
        """Add weather attributes."""
        LOG.debug("Adding weather %s", self._weather)
        return {
            key: self._weather[key]
            for key in self._weather
            if key not in ["temperature", "icon"]
        }

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await super().async_added_to_hass()

    async def _async_update(self):
        self._weather = {}
        self._weather = await self._hilo._api.get_weather(
            self._hilo.devices.location_id
        )
        self._state = self._weather.get("temperature")
