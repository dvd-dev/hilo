from datetime import time
import logging

from homeassistant.components.utility_meter.const import DAILY

LOG = logging.getLogger(__package__)
DOMAIN = "hilo"
HILO_ENERGY_TOTAL = "hilo_energy_total"

# Configurations
CONF_GENERATE_ENERGY_METERS = "generate_energy_meters"
DEFAULT_GENERATE_ENERGY_METERS = False

CONF_HQ_PLAN_NAME = "hq_plan_name"
DEFAULT_HQ_PLAN_NAME = "rate d"

CONF_UNTARIFICATED_DEVICES = "untarificated_devices"
DEFAULT_UNTARIFICATED_DEVICES = False

CONF_LOG_TRACES = "log_traces"
DEFAULT_LOG_TRACES = False

CONF_CHALLENGE_LOCK = "challenge_lock"
DEFAULT_CHALLENGE_LOCK = False

CONF_TRACK_UNKNOWN_SOURCES = "track_unknown_sources"
DEFAULT_TRACK_UNKNOWN_SOURCES = False

CONF_ENERGY_METER_PERIOD = "energy_meter_period"
DEFAULT_ENERGY_METER_PERIOD = DAILY

CONF_APPRECIATION_PHASE = "appreciation_phase"
DEFAULT_APPRECIATION_PHASE = 0

DEFAULT_SCAN_INTERVAL = 60
EVENT_SCAN_INTERVAL = 600
REWARD_SCAN_INTERVAL = 7200
MIN_SCAN_INTERVAL = 15

CONF_TARIFF = {
    "rate d": {
        "low_threshold": 40,
        "low": 0.06319,
        "medium": 0.09749,
        "high": 0,
        "access": 0.42238,
        "reward_rate": 0.55,
    },
    "flex d": {
        "low_threshold": 40,
        "low": 0.04336,
        "medium": 0.07456,
        "high": 0.5065,
        "access": 0.41168,
        "reward_rate": 0.55,
    },
}

CONF_HIGH_PERIODS = {
    "am": {"from": time(6, 00, 00), "to": time(9, 0, 0)},
    "pm": {"from": time(16, 0, 0), "to": time(19, 0, 0)},
}

TARIFF_LIST = ["high", "medium", "low"]

# Class lists
LIGHT_CLASSES = ["LightDimmer", "WhiteBulb", "ColorBulb", "LightSwitch"]
HILO_SENSOR_CLASSES = [
    "SmokeDetector",
    "IndoorWeatherStation",
    "OutdoorWeatherStation",
    "Gateway",
]
CLIMATE_CLASSES = ["Thermostat"]
SWITCH_CLASSES = ["Outlet"]
