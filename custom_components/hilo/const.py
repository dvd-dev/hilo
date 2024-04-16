from datetime import time
import logging

from homeassistant.components.utility_meter.const import DAILY

LOG = logging.getLogger(__package__)
DOMAIN = "hilo"
HILO_ENERGY_TOTAL = "hilo_energy_total"

# Configurations
CONF_APPRECIATION_PHASE = "appreciation_phase"
DEFAULT_APPRECIATION_PHASE = 0

CONF_CHALLENGE_LOCK = "challenge_lock"
DEFAULT_CHALLENGE_LOCK = False

CONF_ENERGY_METER_PERIOD = "energy_meter_period"
DEFAULT_ENERGY_METER_PERIOD = DAILY

CONF_GENERATE_ENERGY_METERS = "generate_energy_meters"
DEFAULT_GENERATE_ENERGY_METERS = False

CONF_HQ_PLAN_NAME = "hq_plan_name"
DEFAULT_HQ_PLAN_NAME = "rate d"

CONF_LOG_TRACES = "log_traces"
DEFAULT_LOG_TRACES = False

CONF_PRE_COLD_PHASE = "pre_cold_phase"
DEFAULT_PRE_COLD_PHASE = 0

CONF_TRACK_UNKNOWN_SOURCES = "track_unknown_sources"
DEFAULT_TRACK_UNKNOWN_SOURCES = False

CONF_UNTARIFICATED_DEVICES = "untarificated_devices"
DEFAULT_UNTARIFICATED_DEVICES = False

DEFAULT_SCAN_INTERVAL = 300
EVENT_SCAN_INTERVAL = 1800
# During reduction phase, let's refresh the current challenge event
# more often to get the reward numbers
# Note ic-dev21: we'll stay at 300 until proper fix
EVENT_SCAN_INTERVAL_REDUCTION = 300
NOTIFICATION_SCAN_INTERVAL = 1800
MIN_SCAN_INTERVAL = 60
REWARD_SCAN_INTERVAL = 7200

CONF_TARIFF = {
    "rate d": {
        "low_threshold": 40,
        "low": 0.06704,
        "medium": 0.10342,
        "high": 0,
        "access": 0.44810,
        "reward_rate": 0.55,
    },
    "flex d": {
        "low_threshold": 40,
        "low": 0.04719,
        "medium": 0.08116,
        "high": 0.55132,
        "access": 0.44810,
        "reward_rate": 0.55,
    },
}

CONF_HIGH_PERIODS = {
    "am": {"from": time(6, 00, 00), "to": time(9, 0, 0)},
    "pm": {"from": time(16, 0, 0), "to": time(19, 0, 0)},
}

TARIFF_LIST = ["high", "medium", "low"]

WEATHER_CONDITIONS = {
    "Unknown": "mdi:weather-sunny-alert",
    "BlowingSnow": "mdi:weather-snowy-heavy",
    "Clear": "mdi:weather-sunny",
    "Cloudy": "mdi:weather-cloudy",
    "Fair": "mdi:weather-partly-cloudy",
    "Foggy": "mdi:weather-fog",
    "HailSleet": "mdi:weather-hail",
    "MostlyCloudy": "mdi:weather-partly-cloudy",
    "Rain": "mdi:weather-rainy",
    "RainSnow": "mdi:weather-snowy-rainy",
    "Snow": "mdi:weather-snowy",
    "Thunder": "mdi:weather-lightning",
    "Windy": "mdi:weather-windy",
}

# Class lists
LIGHT_CLASSES = ["LightDimmer", "WhiteBulb", "ColorBulb"]
HILO_SENSOR_CLASSES = [
    "SmokeDetector",
    "IndoorWeatherStation",
    "OutdoorWeatherStation",
    "Gateway",
]
CLIMATE_CLASSES = ["Thermostat", "FloorThermostat", "Thermostat24V"]
SWITCH_CLASSES = ["LightSwitch", "Outlet", "Ccr", "Cee"]
