"""Support for Hilo automation systems."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Union

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from pyhilo import API
from pyhilo.const import DEFAULT_STATE_FILE
from pyhilo.device import HiloDevice
from pyhilo.devices import Devices
from pyhilo.exceptions import HiloError, InvalidCredentialsError, WebsocketError
from pyhilo.util import from_utc_timestamp, time_diff
from pyhilo.websocket import WebsocketEvent

from .config_flow import STEP_OPTION_SCHEMA
from .const import (
    CONF_APPRECIATION_PHASE,
    CONF_CHALLENGE_LOCK,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HIGH_PERIODS,
    CONF_HQ_PLAN_NAME,
    CONF_LOG_TRACES,
    CONF_TARIFF,
    CONF_TRACK_UNKNOWN_SOURCES,
    CONF_UNTARIFICATED_DEVICES,
    DEFAULT_APPRECIATION_PHASE,
    DEFAULT_CHALLENGE_LOCK,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_LOG_TRACES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACK_UNKNOWN_SOURCES,
    DEFAULT_UNTARIFICATED_DEVICES,
    DOMAIN,
    HILO_ENERGY_TOTAL,
    LOG,
)

DISPATCHER_TOPIC_WEBSOCKET_EVENT = "pyhilo_websocket_event"
SIGNAL_UPDATE_ENTITY = "pyhilo_device_update_{}"
COORDINATOR_AWARE_PLATFORMS = [Platform.SENSOR]
PLATFORMS = COORDINATOR_AWARE_PLATFORMS + [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SWITCH,
]


@callback
def _async_standardize_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bring a config entry up to current standards."""
    entry_updates = {}
    config_keys = STEP_OPTION_SCHEMA.schema.keys()
    if not entry.unique_id:
        # If the config entry doesn't already have a unique ID, set one:
        entry_updates["unique_id"] = entry.data[CONF_USERNAME]
    if any(x in entry.data for x in config_keys):
        # If an option was provided as part of configuration.yaml, pop it out of
        # the config entry's data and move it to options and the same with other
        # possible options.
        data = {**entry.data}
        entry_updates["data"] = data
        options = {}
        for conf_item in config_keys:
            if attr := data.pop(conf_item, None):
                options[conf_item] = attr
        if len(options):
            entry_updates["options"] = {**entry.options, **options}
    if entry_updates:
        hass.config_entries.async_update_entry(entry, **entry_updates)


@callback
def _async_register_custom_device(
    hass: HomeAssistant, entry: ConfigEntry, device: HiloDevice
) -> None:
    """Register a custom device. This is used to register the
    Hilo gateway and the unknown source tracker."""
    LOG.debug(f"Generating custom device {device}")
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, device.identifier)},
        manufacturer=device.manufacturer,
        model=device.model,
        name=device.name,
    )


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Hilo as config entry."""
    _async_standardize_config_entry(hass, entry)
    current_options = {**entry.options}
    log_traces = current_options.get(CONF_LOG_TRACES, DEFAULT_LOG_TRACES)
    scan_interval = current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    state_yaml = hass.config.path(DEFAULT_STATE_FILE)

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        if entry.data[CONF_TOKEN]:
            LOG.debug("Trying auth with token")
            api = await API.async_auth_refresh_token(
                session=websession,
                provided_refresh_token=entry.data[CONF_TOKEN],
                log_traces=log_traces,
                state_yaml=state_yaml,
            )
        else:
            raise InvalidCredentialsError
    except InvalidCredentialsError as err:
        try:
            LOG.debug(f"Trying auth with username/password: {err}")
            api = await API.async_auth_password(
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
                session=websession,
                log_traces=log_traces,
                state_yaml=state_yaml,
            )
        except (KeyError, InvalidCredentialsError) as err:
            raise ConfigEntryAuthFailed from err
    except HiloError as err:
        LOG.error("Config entry failed: %s", err)
        raise ConfigEntryNotReady from err

    hilo = Hilo(hass, entry, api)
    try:
        await hilo.async_init(scan_interval)
    except HiloError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = hilo

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )

    async def async_reload_entry(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Handle an options update.
        This method will get called in two scenarios:
          1. When HiloOptionsFlowHandler is initiated
          2. When a new refresh token is saved to the config entry data
        We only want #1 to trigger an actual reload.
        """
        nonlocal current_options
        updated_options = {**updated_entry.options}
        if updated_options == current_options:
            return

        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hilo config entry."""
    LOG.debug("Unloading entry")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        LOG.debug("Entry unloaded")
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class Hilo:
    """Define a Hilo data object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: API) -> None:
        """Initialize."""
        self._api = api
        self._hass = hass
        self.entry = entry
        self.devices: Devices = Devices(api)
        self._websocket_reconnect_task: asyncio.Task | None = None
        self._update_task: asyncio.Task | None = None
        self.invocations = {
            0: self.subscribe_to_location,
            1: self.subscribe_to_attributes,
        }
        self.hq_plan_name = entry.options.get(CONF_HQ_PLAN_NAME, DEFAULT_HQ_PLAN_NAME)
        self.appreciation = entry.options.get(
            CONF_APPRECIATION_PHASE, DEFAULT_APPRECIATION_PHASE
        )
        self.challenge_lock = entry.options.get(
            CONF_CHALLENGE_LOCK, DEFAULT_CHALLENGE_LOCK
        )
        self.track_unknown_sources = entry.options.get(
            CONF_TRACK_UNKNOWN_SOURCES, DEFAULT_TRACK_UNKNOWN_SOURCES
        )
        self.untarificated_devices = entry.options.get(
            CONF_UNTARIFICATED_DEVICES, DEFAULT_UNTARIFICATED_DEVICES
        )
        self.generate_energy_meters = entry.options.get(
            CONF_GENERATE_ENERGY_METERS, DEFAULT_GENERATE_ENERGY_METERS
        )
        # This will get filled in by async_init:
        self.coordinator: DataUpdateCoordinator | None = None
        self.unknown_tracker_device: HiloDevice | None = None
        if self.track_unknown_sources:
            self._api._get_device_callbacks = [self._get_unknown_source_tracker]

    def validate_heartbeat(self, event: WebsocketEvent) -> None:
        heartbeat_time = from_utc_timestamp(event.arguments[0])  # type: ignore
        if self._api.log_traces:
            LOG.debug(f"Heartbeat: {time_diff(heartbeat_time, event.timestamp)}")

    @callback
    async def on_websocket_event(self, event: WebsocketEvent) -> None:
        """Define a callback for receiving a websocket event."""
        async_dispatcher_send(self._hass, DISPATCHER_TOPIC_WEBSOCKET_EVENT, event)
        if event.event_type == "COMPLETE":
            cb = self.invocations.get(event.invocation)
            if cb:
                async_call_later(self._hass, 3, cb(event.invocation))
        elif event.target == "Heartbeat":
            self.validate_heartbeat(event)
        elif event.target == "DevicesValuesReceived":
            # When receiving attribute values for unknown devices, assume
            # we have refresh the device list.
            new_devices = any(
                self.devices.find_device(item["deviceId"]) is None
                for item in event.arguments[0]
            )
            if new_devices:
                await self.devices.update()

            updated_devices = self.devices.parse_values_received(event.arguments[0])
            # NOTE(dvd): If we don't do this, we need to wait until the coordinator
            # runs (scan_interval) to have updated data in the dashboard.
            for device in updated_devices:
                async_dispatcher_send(
                    self._hass, SIGNAL_UPDATE_ENTITY.format(device.id)
                )
        elif event.target == "DeviceListInitialValuesReceived":
            # This websocket event only happens on initial connection
            # This triggers an update without throwing an exception
            await self.devices.update()                
        elif event.target == "DevicesListChanged":
            # DeviceListChanged only triggers when unpairing devices
            # Forcing an update when that happens, even though pyhilo doesn't
            # manage device removal currently.
            await self.devices.update()
        elif event.target == "GatewayValuesReceived":
            # Gateway deviceId hardcoded to 1 as it is not returned by Gateways/Info. 
            # First time we encounter a GatewayValueReceived event, update device with proper deviceid.
            gateway = self.devices.find_device(1)
            if not gateway is None:
                gateway.id = event.arguments[0][0]["deviceId"]
                LOG.debug("Updated Gateway's deviceId from default 1 to {gateway.id}")

            updated_devices = self.devices.parse_values_received(event.arguments[0])
            # NOTE(dvd): If we don't do this, we need to wait until the coordinator
            # runs (scan_interval) to have updated data in the dashboard.
            for device in updated_devices:
                async_dispatcher_send(
                    self._hass, SIGNAL_UPDATE_ENTITY.format(device.id)
                )
        else:
            LOG.warning(f"Unhandled websocket event: {event}")

    @callback
    async def subscribe_to_location(self, inv_id: int) -> None:
        """Sends the json payload to receive updates from the location."""
        LOG.debug(f"Subscribing to location {self.devices.location_id}")
        await self._api.websocket.async_invoke(
            [self.devices.location_id], "SubscribeToLocation", inv_id
        )

    @callback
    async def subscribe_to_attributes(self, inv_id: int) -> None:
        """Sends the json payload to receive the device attributes."""
        LOG.debug(f"Subscribing to attributes {self.devices.attributes_list}")
        await self._api.websocket.async_invoke(
            self.devices.attributes_list, "SubscribeDevicesAttributes", inv_id
        )

    @callback
    async def request_status_update(self) -> None:
        await self._api.websocket.send_status()
        for inv_id, inv_cb in self.invocations.items():
            await inv_cb(inv_id)

    @callback
    def _get_unknown_source_tracker(self) -> HiloDevice:
        return {
            "name": "Unknown Source Tracker",
            "Disconnected": False,
            "type": "Tracker",
            "category": "Tracker",
            "supportedAttributes": "Power",
            "settableAttributes": "",
            "id": 0,
            "identifier": "hass-hilo-unknown_source_tracker",
            "provider": 0,
            "model_number": "Hass-hilo-2022.1",
            "sw_version": "0.0.1",
        }

    async def async_init(self, scan_interval: int) -> None:
        """Initialize the Hilo "manager" class."""
        if TYPE_CHECKING:
            assert self._api.refresh_token
            assert self._api.websocket

        await self.devices.async_init()

        _async_register_custom_device(
            self._hass, self.entry, self.devices.find_device(1)
        )
        if self.track_unknown_sources:
            if not self.unknown_tracker_device:
                self.unknown_tracker_device = self.devices.generate_device(
                    self._get_unknown_source_tracker()
                )
                self.unknown_tracker_device.net_consumption = True
            _async_register_custom_device(
                self._hass, self.entry, self.unknown_tracker_device
            )

        self._api.websocket.add_connect_callback(self.request_status_update)
        self._api.websocket.add_event_callback(self.on_websocket_event)
        self._websocket_reconnect_task = asyncio.create_task(
            self.start_websocket_loop()
        )
        # asyncio.create_task(self._api.websocket.async_connect())

        async def websocket_disconnect_listener(_: Event) -> None:
            """Define an event handler to disconnect from the websocket."""
            if TYPE_CHECKING:
                assert self._api.websocket

            if self._api.websocket.connected:
                await self._api.websocket.async_disconnect()

        self.entry.async_on_unload(
            self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, websocket_disconnect_listener
            )
        )
        self.coordinator = DataUpdateCoordinator(
            self._hass,
            LOG,
            name="hilo",
            update_interval=timedelta(seconds=scan_interval),
            update_method=self.async_update,
        )

    async def start_websocket_loop(self) -> None:
        """Start a websocket reconnection loop."""
        if TYPE_CHECKING:
            assert self._api.websocket

        should_reconnect = True

        try:
            await self._api.websocket.async_connect()
            await self._api.websocket.async_listen()
        except asyncio.CancelledError:
            LOG.debug("Request to cancel websocket loop received")
            raise
        except WebsocketError as err:
            LOG.error(f"Failed to connect to websocket: {err}", exc_info=err)
            await self.cancel_websocket_loop()
        except InvalidCredentialsError:
            LOG.warning("Invalid credentials? Refreshing websocket infos")
            await self.cancel_websocket_loop()
            await self._api.refresh_ws_token()
        except Exception as err:  # pylint: disable=broad-except
            LOG.error(
                f"Unknown exception while connecting to websocket: {err}", exc_info=err
            )
            await self.cancel_websocket_loop()

        if should_reconnect:
            LOG.info("Disconnected from websocket; reconnecting in 5 seconds.")
            await asyncio.sleep(5)
            self._websocket_reconnect_task = self._hass.async_create_task(
                self.start_websocket_loop()
            )

    async def cancel_task(self, task) -> None:
        LOG.debug(f"Cancelling task {task}")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                LOG.debug(f"Task {task} successfully canceled")
                task = None
        return task

    async def cancel_websocket_loop(self) -> None:
        """Stop any existing websocket reconnection loop."""
        self._websocket_reconnect_task = await self.cancel_task(
            self._websocket_reconnect_task
        )
        self._update_task = await self.cancel_task(self._update_task)
        if TYPE_CHECKING:
            assert self._api.websocket
        await self._api.websocket.async_disconnect()

    async def async_update(self) -> None:
        """Updates tarif periodically."""
        if self.generate_energy_meters:
            self.check_tarif()

    def set_state(self, entity, state, new_attrs={}, keep_state=False, force=False):
        params = f"entity={entity}, state={state}, new_attrs={new_attrs}, keep_state={keep_state}"
        current = self._hass.states.get(entity)
        if not current:
            if not force:
                LOG.warning(f"Unable to set state because there's no current: {params}")
                return
            attrs = {}
        else:
            attrs = dict(current.as_dict()["attributes"])
        LOG.debug(f"Setting state {params} {current}")
        attrs["last_update"] = datetime.now()
        attrs = {**attrs, **new_attrs}
        if keep_state and current:
            state = current.state
        if "Cost" in attrs:
            attrs["Cost"] = state
        self._hass.states.async_set(entity, state, attrs)

    @property
    def high_times(self):
        for period, data in CONF_HIGH_PERIODS.items():
            if data["from"] <= datetime.now().time() <= data["to"]:
                return True
        return False

    def check_tarif(self):
        tarif = "low"
        base_sensor = f"sensor.{HILO_ENERGY_TOTAL}_low"
        energy_used = self._hass.states.get(base_sensor)
        if not energy_used:
            LOG.warning(f"check_tarif: Unable to find state for {base_sensor}")
            return tarif
        plan_name = self.hq_plan_name
        tarif_config = CONF_TARIFF.get(plan_name)
        current_cost = self._hass.states.get("sensor.hilo_rate_current")
        try:
            if float(energy_used.state) >= tarif_config.get("low_threshold"):
                tarif = "medium"
        except ValueError:
            LOG.warning(
                f"Unable to restore a valid state of {base_sensor}: {energy_used.state}"
            )

        if tarif_config.get("high", 0) > 0 and self.high_times:
            tarif = "high"
        target_cost = self._hass.states.get(f"sensor.hilo_rate_{tarif}")
        if target_cost.state != current_cost.state:
            LOG.debug(
                f"check_tarif: Updating current cost, was {current_cost.state} now {target_cost.state}"
            )
            self.set_state("sensor.hilo_rate_current", target_cost.state)
        LOG.debug(
            f"check_tarif: Current plan: {plan_name} Target Tarif: {tarif} Energy used: {energy_used.state} Peak: {self.high_times}"
        )
        known_power = 0
        smart_meter = "sensor.smartenergymeter_power"
        smart_meter_alternate = "sensor.meter00_power"
        unknown_source_tracker = "sensor.unknown_source_tracker_power"
        for state in self._hass.states.async_all():
            entity = state.entity_id
            self.set_tarif(entity, state.state, tarif)
            if entity.endswith("_power") and entity not in [
                unknown_source_tracker,
                smart_meter,
                smart_meter_alternate,
            ]:
                try:
                    known_power += int(float(state.state))
                except ValueError:
                    pass
            if not entity.startswith("sensor.hilo_energy") or entity.endswith("_cost"):
                continue
            self.fix_utility_sensor(entity, state)
        if self.track_unknown_sources:
            total_power = self._hass.states.get(smart_meter)
            if not total_power:
                total_power = self._hass.states.get(smart_meter_alternate)
            unknown_power = int(total_power.state) - known_power
            self.devices.parse_values_received(
                [
                    {
                        "deviceId": 0,
                        "locationId": self.devices.location_id,
                        "timeStampUTC": datetime.utcnow().isoformat(),
                        "attribute": "Power",
                        "value": unknown_power,
                        "valueType": "Watt",
                    }
                ]
            )
            LOG.debug(
                f"Currently in use: Total: {total_power.state} Known sources: {known_power} Unknown sources: {unknown_power}"
            )

    @callback
    def fix_utility_sensor(self, entity, state):
        """not sure why this doesn't get created with a proper device_class"""
        current_state = state.as_dict()
        attrs = current_state.get("attributes", {})
        if not attrs.get("source"):
            LOG.debug(f"No source entity defined on {entity}: {current_state}")
            return
        parent_unit = self._hass.states.get(attrs.get("source"))
        if not parent_unit:
            LOG.warning(f"Unable to find state for parent unit: {current_state}")
            return
        new_attrs = {
            ATTR_UNIT_OF_MEASUREMENT: parent_unit.as_dict()
            .get("attributes", {})
            .get(ATTR_UNIT_OF_MEASUREMENT),
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        }
        if not all(a in attrs.keys() for a in new_attrs.keys()):
            LOG.warning(
                f"Fixing utility sensor: {entity} {current_state} new_attrs: {new_attrs}"
            )
            self.set_state(entity, None, new_attrs=new_attrs, keep_state=True)

    @callback
    def set_tarif(self, entity, current, new):
        if self.untarificated_devices and entity != f"select.{HILO_ENERGY_TOTAL}":
            return
        if entity.startswith("select.hilo_energy") and current != new:
            LOG.debug(
                f"check_tarif: Changing tarif of {entity} from {current} to {new}"
            )
            context = Context()
            data = {ATTR_OPTION: new, "entity_id": entity}
            self._hass.async_create_task(
                self._hass.services.async_call(
                    SELECT_DOMAIN, SERVICE_SELECT_OPTION, data, context=context
                )
            )


class HiloEntity(CoordinatorEntity):
    """Define a base Hilo base entity."""

    def __init__(
        self,
        hilo: Hilo,
        name: Union[str, None] = None,
        *,
        device: HiloDevice | None = None,
    ) -> None:
        """Initialize."""
        assert hilo.coordinator
        super().__init__(hilo.coordinator)
        try:
            gateway = device.gateway_external_id
        except AttributeError:
            gateway = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.identifier)},
            manufacturer=device.manufacturer,
            model=device.model,
            name=device.name,
            via_device=(DOMAIN, gateway),
        )
        if not name:
            name = device.name
        self._attr_name = name
        self._device = device
        self._hilo = hilo
        self._device._entity = self

    @property
    def should_poll(self) -> bool:
        return False if self._device.type != "Gateway" else True

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._device.available

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        raise NotImplementedError()

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._remove_signal_update = async_dispatcher_connect(
            self._hilo._hass,
            SIGNAL_UPDATE_ENTITY.format(self._device.id),
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        self._remove_signal_update()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # Ignore manual update requests if the entity is disabled
        if not self.enabled:
            return

        if self._device.type != "Gateway":
            await self.coordinator.async_request_refresh()
