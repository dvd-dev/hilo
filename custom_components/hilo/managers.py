from collections import OrderedDict
from datetime import timedelta

from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.utility_meter import async_setup as utility_setup
from homeassistant.components.utility_meter.const import DOMAIN as UTILITY_DOMAIN
from homeassistant.components.utility_meter.sensor import (
    async_setup_platform as utility_setup_platform,
)

from .const import HILO_ENERGY_TOTAL, LOG


class UtilityManager:
    """Class that maps to the utility_meters"""

    def __init__(self, hass, period):
        self.hass = hass
        self.period = period
        self.meter_configs = OrderedDict()
        self.meter_entities = {}
        self.new_entities = 0

    def add_meter(self, entity, tariff_list, net_consumption=False):
        self.add_meter_entity(entity, tariff_list)
        self.add_meter_config(entity, tariff_list, net_consumption)

    def add_meter_entity(self, entity, tariff_list):
        if entity in self.hass.data.get("utility_meter_data", {}):
            LOG.debug(f"Entity {entity} is already in the utility meters")
            return
        self.new_entities += 1
        for tarif in tariff_list:
            name = f"{entity}_{self.period}"
            meter_name = f"{name} {tarif}"
            LOG.debug(f"Creating UtilityMeter entity for {entity}: {meter_name}")
            self.meter_entities[meter_name] = {
                "meter": entity,
                "name": meter_name,
                "tariff": tarif,
            }

    def add_meter_config(self, entity, tariff_list, net_consumption):
        name = f"{entity}_{self.period}"
        LOG.debug(
            f"Creating UtilityMeter config: {name} {tariff_list} (Net Consumption: {net_consumption})"
        )
        self.meter_configs[entity] = OrderedDict(
            {
                "source": f"sensor.{entity}",
                "name": name,
                "cycle": self.period,
                "tariffs": tariff_list,
                "net_consumption": net_consumption,
                "utility_meter_sensors": [],
                "offset": timedelta(0),
                "delta_values": False,
            }
        )

    async def update(self, async_add_entities):
        LOG.debug(f"Setting up UtilityMeter entities {UTILITY_DOMAIN}")
        if self.new_entities == 0:
            LOG.debug("No new entities, not setting up again")
            return
        config = {}
        config[UTILITY_DOMAIN] = OrderedDict(
            {**self.hass.data.get("utility_meter_data", {}), **self.meter_configs}
        )
        await utility_setup(self.hass, config)
        await utility_setup_platform(
            self.hass, config, async_add_entities, self.meter_entities
        )


class EnergyManager:
    def __init__(self):
        self.updated = False

    @property
    def msg(self):
        return {
            "energy_sources": self.src,
            "device_consumption": self.dev,
        }

    @property
    def default_flows(self):
        return {
            "type": "grid",
            "flow_from": [],
            "flow_to": [],
            "cost_adjustment_day": 0.0,
        }

    async def init(self, hass, period):
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
        LOG.debug(f"Adding {sensor} / {rate} to grid source")
        self.src[0]["flow_from"].append(flow)

    def add_device(self, sensor):
        sensor = f"sensor.{sensor}"
        if any(d["stat_consumption"] == sensor for d in self.dev):
            return
        LOG.debug(f"Adding {sensor} to individual device consumption")
        self.updated = True
        self.dev.append({"stat_consumption": sensor})

    def add_to_dashboard(self, entity, tariff_list):
        for tarif in tariff_list:
            name = f"{entity}_{self.period}"
            if entity == HILO_ENERGY_TOTAL:
                self.add_flow_from(f"{name}_{tarif}", f"hilo_rate_{tarif}")
            else:
                self.add_device(f"{name}_{tarif}")

    async def update(self):
        if not self.updated:
            return
        LOG.debug("Pushing config to the energy dashboard")
        await self._manager.async_update(self.msg)
        self.updated = False
