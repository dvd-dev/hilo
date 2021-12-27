from datetime import time
import logging

from homeassistant.components.utility_meter.const import DAILY

LOG = logging.getLogger(__package__)
DOMAIN = "hilo"

CONF_GENERATE_ENERGY_METERS = "generate_energy_meters"
DEFAULT_GENERATE_ENERGY_METERS = False

CONF_HQ_PLAN_NAME = "hq_plan_name"
DEFAULT_HQ_PLAN_NAME = "rate d"
CONF_ENERGY_METER_PERIOD = "energy_meter_period"
DEFAULT_ENERGY_METER_PERIOD = DAILY
TARIFF_LIST = ["high", "medium", "low"]

HILO_ENERGY_TOTAL = "hilo_energy_total"

DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15

LIGHT_CLASSES = ["LightDimmer", "WhiteBulb", "ColorBulb", "LightSwitch"]
# Useless for now
HILO_SENSOR_CLASSES = ["SmokeDetector", "IndoorWeatherStation", "OutdoorWeatherStation"]
CLIMATE_CLASSES = ["Thermostat"]
SWITCH_CLASSES = []

CONF_TARIFF = {
    "rate d": {
        "low_threshold": 40,
        "low": 0.06159,
        "medium": 0.09502,
        "high": 0,
        "access": 0.41168,
    },
    "flex d": {
        "low_threshold": 40,
        "low": 0.04336,
        "medium": 0.07456,
        "high": 0.5065,
        "access": 0.41168,
    },
}

CONF_HIGH_PERIODS = {
    "am": {"from": time(6, 00, 00), "to": time(9, 0, 0)},
    "pm": {"from": time(16, 0, 0), "to": time(19, 0, 0)},
}
