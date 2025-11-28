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
MAX_SUB_INTERVAL = 120
MIN_SCAN_INTERVAL = 60
REWARD_SCAN_INTERVAL = 7200

CONF_TARIFF = {
    "rate d": {
        "low_threshold": 40,
        "low": 0.06905,
        "medium": 0.10652,
        "high": 0,
        "access": 0.46154,
        "reward_rate": 0.56785,
    },
    "flex d": {
        "low_threshold": 40,
        "low": 0.04774,
        "medium": 0.08699,
        "high": 0.45088,
        "access": 0.46154,
        "reward_rate": 0.55,
    },
}


TARIFF_LIST = ["high", "medium", "low"]

WEATHER_CONDITIONS = {
    "Unknown": "mdi:weather-sunny-alert",
    "Blowing Snow": "mdi:weather-snowy-heavy",
    "Clear": "mdi:weather-sunny",
    "Cloudy": "mdi:weather-cloudy",
    "Fair": "mdi:weather-partly-cloudy",
    "Foggy": "mdi:weather-fog",
    "Hail Sleet": "mdi:weather-hail",
    "Mostly Cloudy": "mdi:weather-partly-cloudy",
    "Rain": "mdi:weather-rainy",
    "Rain Snow": "mdi:weather-snowy-rainy",
    "Snow": "mdi:weather-snowy",
    "Thunder": "mdi:weather-lightning",
    "Windy": "mdi:weather-windy",
}

# Class lists
LIGHT_CLASSES = ["LightDimmer", "WhiteBulb", "ColorBulb", "LightSwitch"]
HILO_SENSOR_CLASSES = [
    "SmokeDetector",
    "IndoorWeatherStation",
    "OutdoorWeatherStation",
    "Gateway",
]
CLIMATE_CLASSES = ["Thermostat", "FloorThermostat", "Thermostat24V"]
SWITCH_CLASSES = ["Outlet", "Ccr", "Cee"]
