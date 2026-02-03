"""Support for Hilo automation systems."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta
import traceback
from typing import TYPE_CHECKING, List, Optional

from aiohttp import CookieJar, client_exceptions
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
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from pyhilo import API
from pyhilo.device import HiloDevice
from pyhilo.devices import Devices
from pyhilo.event import Event
from pyhilo.exceptions import (
    CannotConnectError,
    HiloError,
    InvalidCredentialsError,
    WebsocketError,
)
from pyhilo.graphql import GraphQlHelper
from pyhilo.util import from_utc_timestamp, time_diff
from pyhilo.websocket import WebsocketEvent, websocket_event_from_payload

from .config_flow import STEP_OPTION_SCHEMA, HiloFlowHandler
from .const import (
    CONF_APPRECIATION_PHASE,
    CONF_CHALLENGE_LOCK,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_LOG_TRACES,
    CONF_PRE_COLD_PHASE,
    CONF_TARIFF,
    CONF_TRACK_UNKNOWN_SOURCES,
    CONF_UNTARIFICATED_DEVICES,
    DEFAULT_APPRECIATION_PHASE,
    DEFAULT_CHALLENGE_LOCK,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_LOG_TRACES,
    DEFAULT_PRE_COLD_PHASE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACK_UNKNOWN_SOURCES,
    DEFAULT_UNTARIFICATED_DEVICES,
    DOMAIN,
    HILO_ENERGY_TOTAL,
    LOG,
    MIN_SCAN_INTERVAL,
)
from .oauth2 import AuthCodeWithPKCEImplementation

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
    """Register a custom device.

    This is used to register the Hilo gateway and the unknown source tracker.
    """
    LOG.debug("Generating custom device %s", device)
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
    HiloFlowHandler.async_register_implementation(
        hass, AuthCodeWithPKCEImplementation(hass)
    )

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    current_options = {**entry.options}

    try:
        api = await API.async_create(
            session=async_create_clientsession(
                hass, cookie_jar=CookieJar(quote_cookie=False)
            ),
            oauth_session=config_entry_oauth2_flow.OAuth2Session(
                hass, entry, implementation
            ),
            log_traces=current_options.get(CONF_LOG_TRACES, DEFAULT_LOG_TRACES),
        )

    except (TimeoutError, client_exceptions.ClientConnectorError):
        LOG.debug("Timeout")
        raise ConfigEntryNotReady

    except Exception as err:
        raise ConfigEntryAuthFailed(err) from err

    _async_standardize_config_entry(hass, entry)
    scan_interval = current_options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    scan_interval = (
        scan_interval if scan_interval >= MIN_SCAN_INTERVAL else MIN_SCAN_INTERVAL
    )

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

    async def handle_debug_event(event: Event):
        """Handle an event."""
        LOG.debug("HILO_DEBUG: Event received: %s", event)
        log_traces = current_options.get(CONF_LOG_TRACES)
        LOG.debug("HILO_DEBUG: log_traces is %s", log_traces)
        websocket_event = websocket_event_from_payload(event.data)
        LOG.debug("HILO_DEBUG: Websocket event parsed: %s", websocket_event)
        await hilo.on_websocket_event(websocket_event)

    log_traces = current_options.get(CONF_LOG_TRACES)
    if log_traces:
        LOG.debug("HILO_DEBUG: log_traces is %s", log_traces)
        hass.bus.async_listen("hilo_debug", handle_debug_event)

    async def async_reload_entry(_: HomeAssistant, updated_entry: ConfigEntry) -> None:
        """Handle an options update.

        This method will get called in two scenarios:
          1. When HiloOptionsFlowHandler is initiated
          2. When a new refresh token is saved to the config entry data
        We only want #1 to trigger an actual reload.
        """
        updated_options = {**updated_entry.options}
        if updated_options == current_options:
            return

        await hass.config_entries.async_reload(entry.entry_id)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Hilo config entry."""
    LOG.debug("Unloading Hilo Integration")

    hilo = hass.data[DOMAIN][entry.entry_id]

    hilo.should_websocket_reconnect = False

    for task in list(hilo._websocket_reconnect_tasks):
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    try:
        if hasattr(hilo, "_devicehub_ws") and hilo._devicehub_ws:
            await hilo._devicehub_ws.async_disconnect()
        if hasattr(hilo, "_challengehub_ws") and hilo._challengehub_ws:
            await hilo._challengehub_ws.async_disconnect()
    except Exception as err:
        LOG.error(f"Error disconnecting websockets: {err}")

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        try:
            if hasattr(hilo, "_api") and hilo._api and hasattr(hilo._api, "session"):
                if hilo._api.session and not hilo._api.session.closed:
                    await hilo._api.session.close()
                    LOG.debug("Session closed")
        except Exception as err:
            LOG.error(f"Error closing session: {err}")

        LOG.debug("Hilo Integration unloaded")
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOG.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        config_entry.version = 2
        hass.config_entries.async_update_entry(
            config_entry, unique_id="hilo", data={"auth_implementation": "hilo"}
        )

    LOG.debug("Migration to version %s successful", config_entry.version)

    return True


class Hilo:
    """Define a Hilo data object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: API) -> None:
        """Initialize."""
        self._api = api
        self._hass = hass
        self.find_meter(self._hass)
        self.entry = entry
        self.devices: Devices = Devices(api)
        self.graphql_helper: GraphQlHelper = GraphQlHelper(api, self.devices)
        self.challenge_id = 0
        self._should_websocket_reconnect = True
        self._websocket_reconnect_tasks: list[asyncio.Task | None] = [None, None]
        self._update_task: list[asyncio.Task | None] = [None, None]
        self.subscriptions: List[Optional[asyncio.Task]] = [None]
        self.invocations = {
            0: self.subscribe_to_location,
            1: self.subscribe_to_challenge,
            2: self.subscribe_to_challengelist,
        }
        self.hq_plan_name = entry.options.get(CONF_HQ_PLAN_NAME, DEFAULT_HQ_PLAN_NAME)
        self.appreciation = entry.options.get(
            CONF_APPRECIATION_PHASE, DEFAULT_APPRECIATION_PHASE
        )
        self.pre_cold = entry.options.get(CONF_PRE_COLD_PHASE, DEFAULT_PRE_COLD_PHASE)
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
        self._events: dict = {}
        if self.track_unknown_sources:
            self._api._get_device_callbacks = [self._get_unknown_source_tracker]
        self._websocket_listeners = []

    def validate_heartbeat(self, event: WebsocketEvent) -> None:
        """Validate heartbeat messages from the websocket."""
        heartbeat_time = from_utc_timestamp(event.arguments[0])  # type: ignore
        if self._api.log_traces:
            LOG.debug("Heartbeat: %s", time_diff(heartbeat_time, event.timestamp))

    def register_websocket_listener(self, listener):
        """Register a listener for websocket events."""
        LOG.debug("Registering websocket listener: %s", listener.__class__.__name__)
        self._websocket_listeners.append(listener)

    async def _handle_websocket_message(self, event):
        """Process websocket messages and notify listeners."""

        # TODO: ic-dev21: This needs to be cleaned up and optimized
        LOG.debug("Received websocket message type: %s", event)
        target = event.target
        LOG.debug("handle_websocket_message_target %s", target)
        msg_data = event
        LOG.debug("handle_websocket_message_ msg_data %s", msg_data)

        if target in [
            "ChallengeListInitialValuesReceived",
            "EventListInitialValuesReceived",
        ]:
            msg_type = "challenge_list_initial"
        elif target in ["ChallengeAdded", "EventAdded"]:
            msg_type = "challenge_added"
        elif target in [
            "ChallengeDetailsUpdated",
            "ChallengeConsumptionUpdatedValuesReceived",
            "EventCHConsumptionUpdatedValuesReceived",
            "ChallengeDetailsUpdatedValuesReceived",
            "EventCHDetailsUpdatedValuesReceived",
            "EventFlexDetailsUpdatedValuesReceived",
            "ChallengeDetailsInitialValuesReceived",
            "EventCHDetailsInitialValuesReceived",
            "EventFlexDetailsInitialValuesReceived",
            "ChallengeListUpdatedValuesReceived",
            "EventListUpdatedValuesReceived",
        ]:
            msg_type = "challenge_details_update"
        elif target == "EventFlexConsumptionUpdatedValuesReceived":
            LOG.debug("%s message received", target)
            LOG.debug("%s data: %s", target, msg_data)
            return

        # ic-dev21 Notify listeners
        for listener in self._websocket_listeners:
            handler_name = f"handle_{msg_type}"
            if hasattr(listener, handler_name):
                handler = getattr(listener, handler_name)
                try:
                    # ic-dev21 Extract the arguments from the WebsocketEvent object
                    if isinstance(msg_data, WebsocketEvent):
                        arguments = msg_data.arguments
                        if arguments:  # ic-dev21 check if there are arguments
                            await handler(arguments[0])
                        else:
                            LOG.warning(
                                f"SHOULD NOT HAPPEN: Received empty arguments for {msg_type}"
                            )
                    else:
                        LOG.warning(
                            f"SHOULD NOT HAPPEN: Not WebsocketEvent: {msg_data}"
                        )
                        await handler(msg_data)
                except Exception as e:
                    LOG.error(f"Error in websocket handler {handler_name}: {e}")
                    LOG.error(traceback.format_exc())

    async def _handle_challenge_events(self, event: WebsocketEvent) -> None:
        """Handle all challenge-related websocket events."""
        if event.target == "ChallengeDetailsInitialValuesReceived":
            challenge = event.arguments[0]
            LOG.debug(
                "ChallengeDetailsInitialValuesReceived, challenge = %s", challenge
            )
            self.challenge_id = challenge.get("id")

        elif event.target == "ChallengeDetailsUpdatedValuesReceived":
            LOG.debug("ChallengeDetailsUpdatedValuesReceived")

        elif event.target == "ChallengeListUpdatedValuesReceived":
            LOG.debug("ChallengeListUpdatedValuesReceived")
            self.challenge_phase = event.arguments[0][0]["currentPhase"]

        elif event.target == "ChallengeAdded":
            LOG.debug("ChallengeAdded")
            challenge = event.arguments[0]
            self.challenge_id = challenge.get("id")
            await self.subscribe_to_challenge(1, self.challenge_id)

        elif event.target == "ChallengeListInitialValuesReceived":
            LOG.debug("ChallengeListInitialValuesReceived")
            challenges = event.arguments[0]

            for challenge in challenges:
                challenge_id = challenge.get("id")
                self.challenge_phase = challenge.get("currentPhase")
                self.challenge_id = challenge.get("id")
                await self.subscribe_to_challenge(1, challenge_id)

        elif event.target == "EventCHDetailsUpdatedValuesReceived":
            LOG.debug("EventCHDetailsUpdatedValuesReceived")
            data = event.arguments[0]
            if "report" in data:
                report = data["report"]
                event_id = data.get("id")
                LOG.debug("Report for event %s: %s", event_id, report)

    async def _handle_device_events(self, event: WebsocketEvent) -> None:
        """Handle all device-related websocket events."""
        if event.target == "DevicesValuesReceived":
            new_devices = any(
                self.devices.find_device(item["deviceId"]) is None
                for item in event.arguments[0]
            )
            if new_devices:
                LOG.warning(
                    "Device list appears to be desynchronized, forcing a refresh thru the API..."
                )
                await self.devices.update()

            updated_devices = self.devices.parse_values_received(event.arguments[0])
            # NOTE(dvd): If we don't do this, we need to wait until the coordinator
            # runs (scan_interval) to have updated data in the dashboard.
            for device in updated_devices:
                async_dispatcher_send(
                    self._hass, SIGNAL_UPDATE_ENTITY.format(device.id)
                )

        elif event.target == "DeviceListInitialValuesReceived":
            await self.devices.update_devicelist_from_signalr(event.arguments[0])

        elif event.target == "DeviceListUpdatedValuesReceived":
            # This message only contains display information, such as the Device's name (as set in the app), it's groupid, icon, etc.
            # Updating the device name causes issues in the integration, it detects it as a new device and creates a new entity.
            # Ignore this call, for now... (update_devicelist_from_signalr does work, but causes the issue above)
            # await self.devices.update_devicelist_from_signalr(event.arguments[0])
            LOG.debug(
                "Received 'DeviceListUpdatedValuesReceived' message, not implemented yet."
            )

        elif event.target == "DevicesListChanged":
            LOG.debug("Received 'DevicesListChanged' message, not implemented yet.")

        elif event.target == "DeviceAdded":
            devices = [event.arguments[0]]
            await self.devices.update_devicelist_from_signalr(devices)

        elif event.target == "DeviceDeleted":
            LOG.debug("Received 'DeviceDeleted' message, not implemented yet.")

        elif event.target == "GatewayValuesReceived":
            gateway = self.devices.find_device(1)
            if gateway:
                gateway.id = event.arguments[0][0]["deviceId"]
                LOG.debug("Updated Gateway's deviceId from default 1 to %s", gateway.id)

            updated_devices = self.devices.parse_values_received(event.arguments[0])
            for device in updated_devices:
                async_dispatcher_send(
                    self._hass, SIGNAL_UPDATE_ENTITY.format(device.id)
                )

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

        elif "Challenge" in event.target or "Event" in event.target:
            LOG.debug("HILO_DEBUG: Handling challenge/event websocket event: %s", event)
            await self._handle_challenge_events(event)
            await self._handle_websocket_message(event)

        elif "Device" in event.target or event.target == "GatewayValuesReceived":
            await self._handle_device_events(event)

        else:
            LOG.warning(f"Unhandled websocket event: {event}")

    @callback
    async def subscribe_to_location(self, inv_id: int) -> None:
        """Send the json payload to receive updates from the location."""
        LOG.debug("Subscribing to location %s", self.devices.location_id)
        await self._api.websocket_devices.async_invoke(
            [self.devices.location_id], "SubscribeToLocation", inv_id
        )

    @callback
    async def subscribe_to_challenge(self, inv_id: int, event_id: int = 0) -> None:
        """Send the json payload to receive updates from the challenge."""
        LOG.debug("Subscribing to challenge : %s or %s", event_id, self.challenge_id)
        event_id = event_id or self.challenge_id
        LOG.debug("API URN is %s", self._api.urn)
        # Get plan name to connect to the correct challenge hub list
        tarif_config = self.hq_plan_name
        LOG.debug("Event list needed is %s", tarif_config)

        # TODO: This is a fallback but will eventually need to be removed, I expect it to create
        # websocket disconnects once the split is complete.
        LOG.warning(
            "Starting legacy connection to ChallengeHub. Your tarif is %s, and will also attempt connection. This can be safely ignored. This will be deprecated",
            tarif_config,
        )
        await self._api.websocket_challenges.async_invoke(
            [{"locationId": self.devices.location_id, "eventId": event_id}],
            "SubscribeToChallenge",
            inv_id,
        )

        # Subscribe to the correct challenge hub
        if tarif_config == "rate d":
            await self._api.websocket_challenges.async_invoke(
                [{"locationHiloId": self._api.urn, "eventId": event_id}],
                "SubscribeToEventCH",
                inv_id,
            )

        elif tarif_config == "flex d":
            await self._api.websocket_challenges.async_invoke(
                [{"locationHiloId": self._api.urn, "eventId": event_id}],
                "SubscribeToEventFlex",
                inv_id,
            )
        else:
            LOG.warning("Unknown plan name %s, falling back to default", tarif_config)
            await self._api.websocket_challenges.async_invoke(
                [{"locationId": self.devices.location_id, "eventId": event_id}],
                "SubscribeToChallenge",
                inv_id,
            )

    @callback
    async def subscribe_to_challengelist(self, inv_id: int) -> None:
        """Send the json payload to receive updates from the challenge list."""
        # TODO : Rename challegenge functions to Event, fallback on challenge for now
        LOG.debug(
            "Subscribing to challenge list at location %s", self.devices.location_id
        )
        LOG.debug("API URN is %s", self._api.urn)

        await self._api.websocket_challenges.async_invoke(
            [{"locationId": self.devices.location_id}],
            "SubscribeToChallengeList",
            inv_id,
        )

        LOG.debug("Subscribing to event list at location %s", self.devices.location_id)
        await self._api.websocket_challenges.async_invoke(
            [{"locationHiloId": self._api.urn}],
            "SubscribeToEventList",
            inv_id,
        )

    @callback
    async def request_challenge_consumption_update(
        self, inv_id: int, event_id: int = 0
    ) -> None:
        """Send the json payload to receive energy consumption updates from the challenge."""
        event_id = event_id or self.challenge_id

        # TODO: Remove fallback once split is complete
        LOG.debug(
            "Requesting challenge %s consumption update at location %s",
            event_id,
            self.devices.location_id,
        )
        await self._api.websocket_challenges.async_invoke(
            [{"locationId": self.devices.location_id, "eventId": event_id}],
            "RequestChallengeConsumptionUpdate",
            inv_id,
        )

        # Get plan name to request the correct consumption update
        tarif_config = self.hq_plan_name
        LOG.debug("API URN is %s", self._api.urn)
        if tarif_config == "rate d":
            LOG.debug(
                "Requesting event CH consumption update at location %s",
                self.devices.location_id,
            )
            await self._api.websocket_challenges.async_invoke(
                [{"locationHiloId": self._api.urn, "eventId": event_id}],
                "RequestEventCHConsumptionUpdate",
                inv_id,
            )
        elif tarif_config == "flex d":
            LOG.debug(
                "Requesting event Flex consumption update at location %s",
                self.devices.location_id,
            )
            await self._api.websocket_challenges.async_invoke(
                [{"locationHiloId": self._api.urn, "eventId": event_id}],
                "RequestEventFlexConsumptionUpdate",
                inv_id,
            )
        else:
            LOG.debug(
                "Requesting challenge %s consumption update at location %s",
                event_id,
                self.devices.location_id,
            )
            await self._api.websocket_challenges.async_invoke(
                [{"locationId": self.devices.location_id, "eventId": event_id}],
                "RequestChallengeConsumptionUpdate",
                inv_id,
            )

    @callback
    async def request_status_update(self) -> None:
        """Request a status update from the device websocket."""
        await self._api.websocket_devices.send_status()
        for inv_id, inv_cb in self.invocations.items():
            await inv_cb(inv_id)

    @callback
    async def request_status_update_challenge(self) -> None:
        """Request a status update from the challenge websocket."""
        await self._api.websocket_challenges.send_status()
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
            "id": 69420,
            "hilo_id": "AB-A2025",
            "identifier": "hass-hilo-unknown_source_tracker",
            "provider": 0,
            "model_number": "Hass-hilo-2025.5",
            "sw_version": "0.0.1",
        }

    async def get_event_details(self, event_id: int):
        """Get events from Hilo only when necessary, otherwise, we hit the cache.

        When preheat is started and our last update is before
        the preheat_start, we refresh. This should update the
        allowed_kWh, etc. values.
        """
        if event_data := self._events.get(event_id):
            event = Event(**event_data)
            if event.invalid:
                LOG.debug(
                    "Invalidating cache for event %s during %s phase (event.current_phase_times=%s event.last_update=%s)",
                    event_id,
                    event.state,
                    event.current_phase_times,
                    event.last_update,
                )
                del self._events[event_id]
            """
            Note ic-dev21: temp fix until we an make it prettier.
            During appreciation, pre-heat and reduction we delete
            the event attributes and reload them with the next if,
            the rest of time time we're reading it from cache
            """

            if event.state in ["appreciation", "pre_heat", "reduction"]:
                LOG.debug(
                    "Invalidating cache for event %s during appreciation, pre_heat or reduction phase (event.last_update=%s)",
                    event_id,
                    event.last_update,
                )
                del self._events[event_id]

        if event_id not in self._events:
            self._events[event_id] = await self._api.get_gd_events(
                self.devices.location_id, event_id=event_id
            )
        return self._events[event_id]

    async def async_init(self, scan_interval: int) -> None:
        """Initialize the Hilo "manager" class."""
        if TYPE_CHECKING:
            assert self._api.refresh_token
            assert self._api.websocket

        await self.devices.async_init()
        await self.graphql_helper.async_init()
        self.subscriptions[0] = asyncio.create_task(
            self.graphql_helper.subscribe_to_device_updated(
                self.devices.location_hilo_id,
                self.handle_subscription_result,
            )
        )

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

        self._api.websocket_devices.add_connect_callback(self.request_status_update)
        self._api.websocket_devices.add_event_callback(self.on_websocket_event)
        self._api.websocket_challenges.add_connect_callback(
            self.request_status_update_challenge
        )
        self._api.websocket_challenges.add_event_callback(self.on_websocket_event)
        self._websocket_reconnect_tasks[0] = asyncio.create_task(
            self.start_websocket_loop(self._api.websocket_devices, 0)
        )
        self._websocket_reconnect_tasks[1] = asyncio.create_task(
            self.start_websocket_loop(self._api.websocket_challenges, 1)
        )

        # asyncio.create_task(self._api.websocket_devices.async_connect())

        async def websocket_disconnect_listener(_: Event) -> None:
            """Define an event handler to disconnect from the websocket."""
            if TYPE_CHECKING:
                assert self._api.websocket_devices

            if self._api.websocket_devices.connected:
                await self._api.websocket_devices.async_disconnect()

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

    async def start_websocket_loop(self, websocket, id) -> None:
        """Start a websocket reconnection loop."""
        if TYPE_CHECKING:
            assert websocket

        try:
            await websocket.async_connect()
            await websocket.async_listen()
        except asyncio.CancelledError:
            LOG.debug("Request to cancel websocket loop received")
            raise
        except CannotConnectError as err:
            if "Session is closed" in str(err):
                LOG.warning(
                    "Session is closed, Home Assistant is probably shutting down"
                )
                self.should_websocket_reconnect = False
                return
        except WebsocketError as err:
            LOG.error(f"Failed to connect to websocket: {err}", exc_info=err)
            await self.cancel_websocket_loop(websocket, id)
        except InvalidCredentialsError:
            LOG.warning("Invalid credentials? Refreshing websocket infos")
            await self.cancel_websocket_loop(websocket, id)
            try:
                await self._api.refresh_ws_token()
            except Exception as err:
                LOG.error(f"Exception while refreshing the token: {err}", exc_info=err)
        except Exception as err:  # pylint: disable=broad-except
            LOG.error(
                f"Unknown exception while connecting to websocket: {err}", exc_info=err
            )
            await self.cancel_websocket_loop(websocket, id)

        if self.should_websocket_reconnect:
            LOG.info("Disconnected from websocket; reconnecting in 5 seconds.")
            await asyncio.sleep(5)
            self._websocket_reconnect_tasks[id] = self._hass.async_create_task(
                self.start_websocket_loop(websocket, id)
            )

    async def cancel_task(self, task) -> None:
        """Cancel a task."""
        LOG.debug("Cancelling task %s", task)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                LOG.debug("Task %s successfully canceled", task)
                task = None
        return task

    async def cancel_websocket_loop(self, websocket, id) -> None:
        """Stop any existing websocket reconnection loop."""
        self._websocket_reconnect_tasks[id] = await self.cancel_task(
            self._websocket_reconnect_tasks[id]
        )
        self._update_task[id] = await self.cancel_task(self._update_task[id])
        if TYPE_CHECKING:
            assert websocket
        await websocket.async_disconnect()

    @property
    def should_websocket_reconnect(self) -> bool:
        """Determine if a websocket should reconnect when the connection is lost.

        Currently only used to disable websockets in the unit tests.
        """
        return self._should_websocket_reconnect

    @should_websocket_reconnect.setter
    def should_websocket_reconnect(self, value: bool) -> None:
        """Set if websocket should reconnect on disconnection."""
        self._should_websocket_reconnect = value

    async def async_update(self) -> None:
        """Update tarif periodically."""
        if self.generate_energy_meters or self.track_unknown_sources:
            self.check_tarif()

        if self.track_unknown_sources:
            self.handle_unknown_power()

    def find_meter(self, hass):
        """Find the smart meter entity in Home Assistant."""
        entity_registry_dict = {}

        registry = hass.data.get("entity_registry")

        if registry is None:
            return entity_registry_dict

        # ic-dev21: Get names of all entities
        for entity_id, entity_entry in registry.entities.items():
            entity_registry_dict[entity_id] = {
                "name": entity_entry.entity_id,
            }

        sorted_entity_registry_dict = OrderedDict(sorted(entity_registry_dict.items()))
        LOG.debug("Entities Ordered dict is %s", sorted_entity_registry_dict)

        # Initialize empty list to put meter name into
        filtered_names = []

        # ic-dev21: Let's grab the meter from our dict
        for entity_id, entity_data in sorted_entity_registry_dict.items():
            if all(
                substring in entity_data["name"] for substring in ["meter", "_power"]
            ):
                filtered_names.append(entity_data["name"])

        LOG.debug("Hilo Smart meter name is: %s", filtered_names)

        # Format output to use in check_tarif
        return ", ".join(filtered_names) if filtered_names else ""

    def set_state(self, entity, state, new_attrs={}, keep_state=False, force=False):
        """Set the state of an entity."""
        params = f"{entity=} {state=} {new_attrs=} {keep_state=}"
        current = self._hass.states.get(entity)
        if not current:
            if not force:
                LOG.warning(f"Unable to set state because there's no current: {params}")
                return
            attrs = {}
        else:
            attrs = dict(current.as_dict()["attributes"])
        attrs["last_update"] = datetime.now()
        attrs["hilo_update"] = True
        attrs = {**attrs, **new_attrs}
        if keep_state and current:
            state = current.state
        if "Cost" in attrs:
            attrs["Cost"] = state
        LOG.debug("Setting state %s current=%s attrs=%s", params, current, attrs)
        self._hass.states.async_set(entity, state, attrs, force_update=force)

    @property
    def high_times(self):
        """Check if the current time is within high tariff periods."""
        challenge_sensor = self._hass.states.get("sensor.defi_hilo")
        LOG.debug(
            "high_times check tarif challenge sensor is %s", challenge_sensor.state
        )
        return challenge_sensor.state == "reduction"

    def check_season(self):
        """Determine if we are using a winter or summer rate."""
        current_month = datetime.now().month
        LOG.debug("check_season current month is %s", current_month)
        return current_month in [12, 1, 2, 3]

    def check_tarif(self):
        """Determine which tarif to select depending on season and user-selected rate."""
        if self.generate_energy_meters:
            season = self.check_season()
            LOG.debug("check_tarif current season state is %s", season)
            tarif = "low"
            base_sensor = f"sensor.{HILO_ENERGY_TOTAL}_low"
            energy_used = self._hass.states.get(base_sensor)
            if not energy_used:
                LOG.warning(f"check_tarif: Unable to find state for {base_sensor}")
                return tarif
            user_selected_plan_name = self.hq_plan_name

            if user_selected_plan_name == "flex d":
                if season:
                    plan_name = "flex d"
                else:
                    plan_name = "rate d"
            else:
                plan_name = user_selected_plan_name

            tarif_config = CONF_TARIFF.get(plan_name)

        for tarif_name, rate in tarif_config.items():
            if rate > 0 and tarif_name in ["low", "medium", "high"]:
                if hasattr(self, "cost_sensors") and tarif_name in self.cost_sensors:
                    sensor = self.cost_sensors[tarif_name]
                    sensor._cost = rate
                    sensor.async_write_ha_state()
                    LOG.debug("check_tarif Updated %s sensor to %s", tarif_name, rate)

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
                "check_tarif: Updating current cost, was %s now %s",
                current_cost.state,
                target_cost.state,
            )
            self.set_state("sensor.hilo_rate_current", target_cost.state)
        LOG.debug(
            "check_tarif: Current plan: %s Target Tarif: %s Energy used: %s Peak: %s",
            plan_name,
            tarif,
            energy_used.state,
            self.high_times,
        )

        # ic-dev21 : make sure the select for all meters still work by moving this here
        for state in self._hass.states.async_all():
            entity = state.entity_id
            self.set_tarif(entity, state.state, tarif)

    def handle_unknown_power(self):
        """Take care of the unknown source meter."""
        known_power = 0
        smart_meter = self.find_meter(self._hass)
        LOG.debug("Smart meter used currently is: %s", smart_meter)
        unknown_source_tracker = "sensor.unknown_source_tracker_power"
        for state in self._hass.states.async_all():
            entity = state.entity_id
            if entity.endswith("hilo_rate_current"):
                continue

            if entity.endswith("_power") and entity not in [
                unknown_source_tracker,
                smart_meter,
            ]:
                try:
                    known_power += int(float(state.state))
                except ValueError:
                    pass
            if not entity.endswith("_hilo_energy") or entity.endswith("_cost"):
                continue
            self.fix_utility_sensor(entity, state)
        if self.track_unknown_sources:
            total_power = self._hass.states.get(smart_meter)
            try:
                if known_power <= int(total_power.state):
                    unknown_power = int(total_power.state) - known_power
                else:
                    unknown_power = 0
            except ValueError:
                unknown_power = known_power
                LOG.warning(
                    f"value of total_power ({total_power} not initialized correctly)"
                )

            self.devices.parse_values_received(
                [
                    {
                        "deviceId": 69420,
                        "locationId": self.devices.location_id,
                        "timeStampUTC": datetime.utcnow().isoformat(),
                        "attribute": "Power",
                        "value": unknown_power,
                        "valueType": "Watt",
                    }
                ]
            )
            LOG.debug(
                "Currently in use: Total: %s Known sources: %s Unknown sources: %s",
                total_power.state,
                known_power,
                unknown_power,
            )

    @callback
    def fix_utility_sensor(self, entity, state):
        """Not sure why this doesn't get created with a proper device_class."""
        current_state = state.as_dict()
        attrs = current_state.get("attributes", {})
        if entity.startswith("select.") or entity.find("hilo_rate") > 0:
            return
        if not attrs.get("source"):
            LOG.debug("No source entity defined on %s: %s", entity, current_state)
            return

        parent_unit_state = self._hass.states.get(attrs.get("source"))
        parent_unit = (
            "kWh"
            if parent_unit_state is None
            else parent_unit_state.attributes.get("unit_of_measurement")
        )
        if not parent_unit:
            LOG.warning(f"Unable to find state for parent unit: {current_state}")
            return

        new_attrs = {
            ATTR_UNIT_OF_MEASUREMENT: parent_unit,  # note ic-dev21: now uses parent_unit directly
            ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
        }
        if not all(a in attrs.keys() for a in new_attrs.keys()):
            LOG.warning(
                f"Fixing utility sensor: {entity} {current_state} new_attrs: {new_attrs}"
            )
            self.set_state(entity, None, new_attrs=new_attrs, keep_state=True)

    @callback
    def set_tarif(self, entity, current, new):
        """Set the tarif on the select entity if needed."""
        if self.untarificated_devices and entity != f"select.{HILO_ENERGY_TOTAL}":
            return
        if entity.startswith("select.hilo_energy") and current != new:
            LOG.debug(
                "check_tarif: Changing tarif of %s from %s to %s", entity, current, new
            )
            context = Context()
            data = {ATTR_OPTION: new, "entity_id": entity}
            self._hass.async_create_task(
                self._hass.services.async_call(
                    SELECT_DOMAIN, SERVICE_SELECT_OPTION, data, context=context
                )
            )
        if (
            entity.startswith("select.")
            and entity.endswith("_hilo_energy")
            and current != new
        ):
            LOG.debug(
                "check_tarif: Changing tarif of %s from %s to %s", entity, current, new
            )
            context = Context()
            data = {ATTR_OPTION: new, "entity_id": entity}
            self._hass.async_create_task(
                self._hass.services.async_call(
                    SELECT_DOMAIN, SERVICE_SELECT_OPTION, data, context=context
                )
            )

    @callback
    def async_migrate_unique_id(
        self, old_unique_id: str, new_unique_id: str | None, platform: str
    ) -> None:
        """Migrate legacy unique IDs to new format."""
        assert new_unique_id is not None
        LOG.debug(
            "Checking if unique ID %s on %s needs to be migrated",
            old_unique_id,
            platform,
        )
        entity_registry = er.async_get(self._hass)
        # async_get_entity_id wants the "HILO" domain
        # in the platform field and the actual platform in the domain
        # field for historical reasons since everything used to be
        # PLATFORM.INTEGRATION instead of INTEGRATION.PLATFORM
        if (
            entity_id := entity_registry.async_get_entity_id(
                platform, DOMAIN, old_unique_id
            )
        ) is None:
            LOG.debug("Unique ID %s does not need to be migrated", old_unique_id)
            return
        if new_entity_id := entity_registry.async_get_entity_id(
            platform, DOMAIN, new_unique_id
        ):
            LOG.debug(
                (
                    "Unique ID %s is already in use by %s (system may have been"
                    " downgraded)"
                ),
                new_unique_id,
                new_entity_id,
            )
            return
        LOG.debug(
            "Migrating unique ID for entity %s (%s -> %s)",
            entity_id,
            old_unique_id,
            new_unique_id,
        )
        entity_registry.async_update_entity(entity_id, new_unique_id=new_unique_id)

    @callback
    def handle_subscription_result(self, hilo_id: str) -> None:
        """Handle subscription result by notifying entities."""
        async_dispatcher_send(self._hass, SIGNAL_UPDATE_ENTITY.format(hilo_id))
