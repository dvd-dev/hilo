"""Support for various Hilo sensors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from os.path import isfile

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
    Platform,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfSoundPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle, slugify
import homeassistant.util.dt as dt_util
from pyhilo.const import UNMONITORED_DEVICES
from pyhilo.device import HiloDevice
from pyhilo.event import Event
from pyhilo.util import from_utc_timestamp
import ruyaml as yaml

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
    EVENT_SCAN_INTERVAL_REDUCTION,
    HILO_ENERGY_TOTAL,
    HILO_SENSOR_CLASSES,
    LOG,
    NOTIFICATION_SCAN_INTERVAL,
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
    """Process Wi-Fi signal strength and return string for display."""
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
        device._energy_entity = EnergySensor(hilo, device)
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
        LOG.debug(f"Adding device {d}")
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
    for tarif, amount in tariff_config.items():
        if amount > 0:
            sensor_name = f"Hilo rate {tarif}"
            cost_entities.append(
                HiloCostSensor(hilo, sensor_name, hq_plan_name, amount)
            )
    cost_entities.append(HiloCostSensor(hilo, "Hilo rate current", hq_plan_name))
    async_add_entities(cost_entities)
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
        self._attr_name = f"{device.name} Battery"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-battery"
        self._attr_unique_id = f"{slugify(device.identifier)}-battery"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
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

    _attr_device_class = SensorDeviceClass.CO2
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} CO2"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-co2"
        self._attr_unique_id = f"{slugify(device.identifier)}-co2"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug(f"Setting up CO2Sensor entity: {self._attr_name}")

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

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(self, hilo, device):
        self._device = device
        self._attr_name = f"{device.name} Hilo Energy"
        old_unique_id = f"hilo_energy_{slugify(device.name)}"
        self._attr_unique_id = f"{slugify(device.identifier)}-energy"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._unit_prefix = None

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
        self._attr_icon = "mdi:lightning-bolt"
        LOG.debug(
            f"Setting up EnergySensor entity: {self._attr_name} with source {self._source}"
        )

    @property
    def unit_of_measurement(self):
        return self._attr_unit_of_measurement

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        LOG.debug(f"Added to hass: {self._attr_name}")
        await super().async_added_to_hass()


class NoiseSensor(HiloEntity, SensorEntity):
    """Define a Netatmo noise sensor entity."""

    _attr_native_unit_of_measurement = UnitOfSoundPressure.DECIBEL
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Noise"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-noise"
        self._attr_unique_id = f"{slugify(device.identifier)}-noise"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
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

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Temperature"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-temperature"
        self._attr_unique_id = f"{slugify(device.identifier)}-temperature"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
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


class TargetTemperatureSensor(HiloEntity, SensorEntity):
    """Define a Hilo target temperature sensor entity."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hilo, device):
        self._attr_name = f"{device.name} Target Temperature"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = f"{slugify(device.name)}-target-temperature"
        self._attr_unique_id = f"{slugify(device.identifier)}-target-temperature"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug(f"Setting up TargetTemperatureSensor entity: {self._attr_name}")

    @property
    def state(self):
        return str(float(self._device.get_value("target_temperature", 0)))

    @property
    def icon(self):
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
    Notifications only used for OneLink's alerts & Low-battery warnings.
    We should consider having this sensor enabled only if a smoke detector is in use.
    """

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Notifications Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug(f"Setting up NotificationSensor entity: {self._attr_name}")
        self.scan_interval = timedelta(seconds=NOTIFICATION_SCAN_INTERVAL)
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

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _entity_component_unrecorded_attributes = frozenset({"history"})

    def __init__(self, hilo, device, scan_interval):
        self._attr_name = "Recompenses Hilo"

        # Check if currency is configured, set a default if not
        currency = hilo._hass.config.currency
        if currency:
            self._attr_native_unit_of_measurement = currency
        else:
            # Set a default currency or handle the case where currency is not configured
            self._attr_native_unit_of_measurement = "CAD"

        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug(f"Setting up RewardSensor entity: {self._attr_name}")
        self._history_state_yaml: str = "hilo_eventhistory_state.yaml"
        self.scan_interval = timedelta(seconds=REWARD_SCAN_INTERVAL)
        self._state = 0
        self._history = self._load_history()
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
            current_history = self._history
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
                        and current_history_event.get("state") == "completed"
                        and event_age > timedelta(days=1)
                    ):
                        # No point updating events for previously completed events, they won't change.
                        event = current_history_event
                    else:
                        details = await self._hilo.get_event_details(raw_event["id"])
                        event = Event(**details).as_dict()

                    events.append(event)
                season["events"] = events
                new_history.append(season)
            self._history = new_history
            self._save_history(new_history)

    def _load_history(self) -> list:
        history: list = []
        if isfile(self._history_state_yaml):
            with open(self._history_state_yaml) as yaml_file:
                LOG.debug("Loading history state from yaml")
                history = yaml.load(yaml_file, Loader=yaml.Loader)
        return history

    def _save_history(self, history: list):
        with open(self._history_state_yaml, "w") as yaml_file:
            LOG.debug("Saving history state to yaml file")
            yaml.dump(history, yaml_file, Dumper=yaml.RoundTripDumper)


class HiloChallengeSensor(HiloEntity, RestoreEntity, SensorEntity):
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
        self._attr_name = "Defi Hilo"
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(self._attr_name)
        self._attr_unique_id = (
            f"{slugify(device.identifier)}-{slugify(self._attr_name)}"
        )
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
        LOG.debug(f"Setting up ChallengeSensor entity: {self._attr_name}")
        # note ic-dev21: scan time at 5 minutes (300s) will force local update
        self.scan_interval = timedelta(seconds=EVENT_SCAN_INTERVAL_REDUCTION)
        self._state = "off"
        self._next_events = []
        self.async_update = Throttle(self.scan_interval)(self._async_update)

    @property
    def state(self):
        if len(self._next_events) > 0:
            event = Event(**{**{"id": 0}, **self._next_events[0]})
            return event.state
        else:
            return "off"

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
        if self.state == "pre_cold":
            return "mdi:radiator-off"
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
        self._next_events = []
        events = await self._hilo._api.get_gd_events(self._hilo.devices.location_id)
        LOG.debug(f"Events received from Hilo: {events}")
        for raw_event in events:
            details = await self._hilo.get_event_details(raw_event["id"])
            event = Event(**details)
            if self._hilo.appreciation > 0:
                event.appreciation(self._hilo.appreciation)
            if self._hilo.pre_cold > 0:
                event.pre_cold(self._hilo.pre_cold)
            self._next_events.append(event.as_dict())


class DeviceSensor(HiloEntity, SensorEntity):
    """Devices like the gateway or Smoke Detectors don't have many attributes,
    except for the "disconnected" attribute. These entities are monitoring
    this state.
    """

    def __init__(self, hilo, device):
        self._attr_name = device.name
        super().__init__(hilo, name=self._attr_name, device=device)
        old_unique_id = slugify(device.name)
        self._attr_unique_id = f"{slugify(device.identifier)}-{slugify(device.name)}"
        hilo.async_migrate_unique_id(
            old_unique_id, self._attr_unique_id, Platform.SENSOR
        )
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


class HiloCostSensor(HiloEntity, RestoreEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = (
        f"{CURRENCY_DOLLAR}/{UnitOfEnergy.KILO_WATT_HOUR}"
    )
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:cash"

    def __init__(self, hilo, name, plan_name, amount=0):
        for d in hilo.devices.all:
            if d.type == "Gateway":
                device = d
        if "low_threshold" in name:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self.data = None
        self._attr_name = name
        self.plan_name = plan_name
        self._amount = amount
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

    async def async_update(self):
        return
