"""Utility and Energy Manager classes for Hilo integration."""

from collections import OrderedDict
from datetime import timedelta

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.utility_meter import async_setup as utility_setup
from homeassistant.components.utility_meter.const import (
    CONF_TARIFFS,
    DOMAIN as UTILITY_DOMAIN,
)
from homeassistant.helpers import entity_registry as er

from .const import HILO_ENERGY_TOTAL, LOG


class UtilityManager:
    """Class that maps to the utility_meters."""

    def __init__(self, hass, period, tariffs):
        """Initialize the utility manager."""
        self.tariffs = tariffs
        self.hass = hass
        self.period = period
        self.meter_configs = OrderedDict()
        self.meter_entities = {}
        self.new_entities = 0

    def add_meter(self, entity, tariff_list, net_consumption=False):
        """Add meter."""
        self.add_meter_entity(entity, tariff_list)
        self.add_meter_config(entity, tariff_list, net_consumption)

    def add_meter_entity(self, entity, tariff_list):
        """Add meter entity."""
        if entity in self.hass.data.get("utility_meter_data", {}):
            LOG.debug("Entity %s is already in the utility meters", entity)
            return
        self.new_entities += 1
        for tarif in tariff_list:
            name = f"{entity}_{self.period}"
            meter_name = f"{name} {tarif}"
            LOG.debug("Creating UtilityMeter entity for %s : %s", entity, meter_name)
            self.meter_entities[meter_name] = {
                "meter": entity,
                "name": meter_name,
                "tariff": tarif,
            }

    def add_meter_config(self, entity, tariff_list, net_consumption):
        """Add meter configuration."""
        name = f"{entity}_{self.period}"
        LOG.debug(
            "Creating UtilityMeter config: %s %s (Net Consumption: %s)",
            name,
            tariff_list,
            net_consumption,
        )
        self.meter_configs[entity] = OrderedDict(
            {
                "source": f"sensor.{entity}",
                "name": name,
                "cycle": self.period,
                CONF_TARIFFS: tariff_list,
                "net_consumption": net_consumption,
                "utility_meter_sensors": [],
                "offset": timedelta(0),
                "delta_values": False,
                "periodically_resetting": True,
                "always_available": True,
            }
        )

    async def update(self, async_add_entities):
        """Update the entities."""
        LOG.debug("=== UtilityManager.update() called ===")
        LOG.debug("Setting up UtilityMeter entities %s", UTILITY_DOMAIN)
        LOG.debug("new_entities count: %d", self.new_entities)

        if self.new_entities == 0:
            LOG.debug("No new entities, not setting up again")
            return

        # Get the entity registry
        registry = er.async_get(self.hass)

        # Filter out entities that already exist
        filtered_configs = OrderedDict()

        for source_entity, config in self.meter_configs.items():
            # Check if any of the tariff entities for this source already exist
            name = config["name"]
            should_include = False

            for tariff in config[CONF_TARIFFS]:
                # Remove period from name to match actual entity ID, this is why the check was failing
                name_without_period = name.replace(f"_{self.period}", "")
                entity_id = f"sensor.{name_without_period.lower().replace(' ', '_')}_{tariff.lower()}"

                if registry.async_get(entity_id) is None:
                    should_include = True
                    LOG.debug(
                        "Entity %s does not exist, will create config for %s",
                        entity_id,
                        source_entity,
                    )
                    break
                else:
                    LOG.debug("Entity %s already exists", entity_id)

            if should_include:
                filtered_configs[source_entity] = config

        if not filtered_configs:
            LOG.debug("All entities already exist, skipping setup")
            self.new_entities = 0
            return

        LOG.debug("Creating utility meter config for %d sources", len(filtered_configs))
        config = {
            UTILITY_DOMAIN: OrderedDict(
                {**self.hass.data.get("utility_meter_data", {}), **filtered_configs}
            ),
            CONF_TARIFFS: self.tariffs,
        }

        # Replaced utility_setup_platform call
        await utility_setup(self.hass, config)
        self.new_entities = 0
        LOG.debug("=== UtilityManager.update() completed ===")


class EnergyManager:
    """Class that manages the energy dashboard configuration."""

    def __init__(self):
        """Initialize the energy manager."""
        self.updated = False

    @property
    def msg(self):
        """Return the message payload for the energy manager."""
        return {
            "energy_sources": self.src,
            "device_consumption": self.dev,
        }

    @property
    def default_flows(self):
        """Return the default grid flow configuration."""
        return {
            "type": "grid",
            "flow_from": [],
            "flow_to": [],
            "cost_adjustment_day": 0.0,
        }

    async def init(self, hass, period):
        """Initialize the energy manager."""
        self.period = period
        self._manager = await async_get_manager(hass)
        data = self._manager.data or self._manager.default_preferences()
        self.prefs = data.copy()
        self.src = self.prefs.get("energy_sources", [])
        self.dev = self.prefs.get("device_consumption", [])
        if not self.src:
            self.src.append(self.default_flows)
        return self

    def add_flow_from(self, sensor, rate):
        """Add grid source flow_from sensor."""
        sensor = f"sensor.{sensor}"
        if any(d["stat_energy_from"] == sensor for d in self.src[0]["flow_from"]):
            return
        self.updated = True
        flow = {
            "stat_energy_from": sensor,
            "stat_cost": None,
            "entity_energy_from": sensor,
            "entity_energy_price": f"sensor.{rate}",
            "number_energy_price": None,
        }
        LOG.debug("Adding %s / %s to grid source", sensor, rate)
        self.src[0]["flow_from"].append(flow)

    def add_device(self, sensor):
        """Add device consumption sensor."""
        sensor = f"sensor.{sensor}"
        if any(d["stat_consumption"] == sensor for d in self.dev):
            return
        LOG.debug("Adding %s to individual device consumption", sensor)
        self.updated = True
        self.dev.append({"stat_consumption": sensor})

    def add_to_dashboard(self, entity, tariff_list):
        """Add entity to the energy dashboard."""
        for tarif in tariff_list:
            name = f"{entity}_{self.period}"
            if entity == HILO_ENERGY_TOTAL:
                self.add_flow_from(f"{name}_{tarif}", f"hilo_rate_{tarif}")
            else:
                self.add_device(f"{name}_{tarif}")

    async def update(self):
        """Push updates to the energy dashboard."""
        if not self.updated:
            return
        LOG.debug("Pushing config to the energy dashboard")
        await self._manager.async_update(self.msg)
        self.updated = False
