"""Tests for Hilo tariff and seasonal rate selection."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hilo import Hilo
from custom_components.hilo.const import (
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_TARIFF,
    DOMAIN,
    HILO_ENERGY_TOTAL,
)
from custom_components.hilo.sensor import HiloCostTotalSensor, async_setup_entry


class DummyCostSensor:
    """Mock cost sensor entity for testing check_tarif."""

    def __init__(self, cost=0.0):
        self._cost = float(cost)
        self.hass = None

    def async_write_ha_state(self):
        """Mock async_write_ha_state."""


def create_mock_hilo(hass: HomeAssistant, hq_plan_name: str = "flex d") -> Hilo:
    """Create a lightweight Hilo instance for unit testing."""
    hilo = Hilo.__new__(Hilo)
    hilo._hass = hass
    hilo.hq_plan_name = hq_plan_name
    hilo.generate_energy_meters = True
    hilo.untarificated_devices = False
    hilo.track_unknown_sources = False
    hilo.cost_sensors = {
        "low": DummyCostSensor(CONF_TARIFF["flex d"]["low"]),
        "medium": DummyCostSensor(CONF_TARIFF["flex d"]["medium"]),
        "high": DummyCostSensor(CONF_TARIFF["flex d"]["high"]),
        "current": DummyCostSensor(0.0),
    }
    return hilo


@pytest.mark.parametrize(
    ("month", "expected_is_winter"),
    [
        (1, True),  # Mid-winter
        (3, True),  # Winter boundary end
        (4, False),  # Summer boundary start
        (7, False),  # Mid-summer
        (11, False),  # Summer boundary end
        (12, True),  # Winter boundary start
    ],
)
def test_check_season(month: int, expected_is_winter: bool):
    """Test season checking on boundary and representative months."""
    hilo = Hilo.__new__(Hilo)
    assert hilo.check_season(datetime(2026, month, 15)) is expected_is_winter


@pytest.mark.parametrize("is_winter", [True, False])
def test_rate_d_rates_all_year(hass: HomeAssistant, is_winter: bool):
    """Test rate d returns Rate D rates year-round and never touches high."""
    hilo = create_mock_hilo(hass, "rate d")
    high_before = hilo.cost_sensors["high"]._cost

    with patch.object(hilo, "check_season", return_value=is_winter):
        assert hilo.plan_name == "rate d"
        assert hilo.get_tariff_config() == CONF_TARIFF["rate d"]
        hilo.check_tarif()

    assert hilo.cost_sensors["low"]._cost == CONF_TARIFF["rate d"]["low"]
    assert hilo.cost_sensors["medium"]._cost == CONF_TARIFF["rate d"]["medium"]
    assert hilo.cost_sensors["high"]._cost == high_before


@pytest.mark.parametrize(
    ("is_winter", "expected_plan", "expected_config"),
    [
        (True, "flex d", CONF_TARIFF["flex d"]),
        (
            False,
            "rate d",
            {
                **CONF_TARIFF["flex d"],
                "low": CONF_TARIFF["rate d"]["low"],
                "medium": CONF_TARIFF["rate d"]["medium"],
            },
        ),
    ],
)
def test_flex_d_rates_by_season(
    is_winter: bool, expected_plan: str, expected_config: dict
):
    """Test flex d returns seasonal baseline rates while keeping high tier."""
    hilo = Hilo.__new__(Hilo)
    hilo.hq_plan_name = "flex d"

    with patch.object(hilo, "check_season", return_value=is_winter):
        assert hilo.plan_name == expected_plan
        assert hilo.get_tariff_config() == expected_config


def test_check_tarif_fresh_install_no_energy_sensor(hass: HomeAssistant):
    """Test check_tarif on fresh install when energy sensors have no state yet."""
    hilo = create_mock_hilo(hass, "flex d")

    # Simulate summer with no energy meter state registered in hass.states
    with patch.object(hilo, "check_season", return_value=False):
        hilo.check_tarif()

    # Rates should update to summer rates and current defaults to low tier
    assert hilo.cost_sensors["low"]._cost == CONF_TARIFF["rate d"]["low"]
    assert hilo.cost_sensors["medium"]._cost == CONF_TARIFF["rate d"]["medium"]
    assert hilo.cost_sensors["high"]._cost == CONF_TARIFF["flex d"]["high"]
    assert hilo.cost_sensors["current"]._cost == CONF_TARIFF["rate d"]["low"]


@pytest.mark.parametrize(
    ("energy_state", "expected_tier"),
    [
        (STATE_UNKNOWN, "low"),
        (STATE_UNAVAILABLE, "low"),
        ("not-a-number", "low"),
        (str(CONF_TARIFF["flex d"]["low_threshold"] - 0.1), "low"),
        (str(CONF_TARIFF["flex d"]["low_threshold"]), "medium"),
        (str(CONF_TARIFF["flex d"]["low_threshold"] + 5.0), "medium"),
    ],
)
def test_check_tarif_low_medium_selection(
    hass: HomeAssistant, energy_state: str, expected_tier: str
):
    """Test check_tarif picks low/medium from daily usage and the threshold."""
    hilo = create_mock_hilo(hass, "flex d")
    hass.states.async_set(f"sensor.{HILO_ENERGY_TOTAL}_low", energy_state)

    with patch.object(hilo, "check_season", return_value=False):
        hilo.check_tarif()

    assert hilo.cost_sensors["current"]._cost == CONF_TARIFF["rate d"][expected_tier]


def test_check_tarif_high_tier_during_challenge(hass: HomeAssistant):
    """Test check_tarif selects high during a challenge reduction period."""
    hilo = create_mock_hilo(hass, "flex d")
    hass.states.async_set("sensor.defi_hilo", "reduction")

    with patch.object(hilo, "check_season", return_value=True):
        hilo.check_tarif()

    assert hilo.cost_sensors["current"]._cost == CONF_TARIFF["flex d"]["high"]


async def test_check_tarif_season_change_transition(hass: HomeAssistant):
    """Test dynamic rate transition when season changes from winter to summer."""
    hilo = create_mock_hilo(hass, "flex d")

    # Winter period
    with patch.object(hilo, "check_season", return_value=True):
        await hilo.async_update()
        assert hilo.cost_sensors["low"]._cost == CONF_TARIFF["flex d"]["low"]
        assert hilo.cost_sensors["medium"]._cost == CONF_TARIFF["flex d"]["medium"]
        assert hilo.cost_sensors["current"]._cost == CONF_TARIFF["flex d"]["low"]

    # Transition to summer period
    with patch.object(hilo, "check_season", return_value=False):
        await hilo.async_update()
        assert hilo.cost_sensors["low"]._cost == CONF_TARIFF["rate d"]["low"]
        assert hilo.cost_sensors["medium"]._cost == CONF_TARIFF["rate d"]["medium"]
        assert hilo.cost_sensors["current"]._cost == CONF_TARIFF["rate d"]["low"]


@pytest.mark.parametrize("is_winter", [True, False])
async def test_sensor_rates_flex_d_initialization(
    hass: HomeAssistant,
    is_winter: bool,
):
    """Test that flex d sensors initialize with correct seasonal rates right away."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": "hilo", "token": "123"},
        options={
            CONF_GENERATE_ENERGY_METERS: True,
            CONF_HQ_PLAN_NAME: "flex d",
        },
        unique_id="hilo",
        version=2,
    )

    expected_low = (
        CONF_TARIFF["flex d"]["low"] if is_winter else CONF_TARIFF["rate d"]["low"]
    )
    expected_med = (
        CONF_TARIFF["flex d"]["medium"]
        if is_winter
        else CONF_TARIFF["rate d"]["medium"]
    )
    expected_high = CONF_TARIFF["flex d"]["high"]

    hilo = create_mock_hilo(hass, "flex d")
    hilo.coordinator = MagicMock()
    hilo.register_signalr_listener = MagicMock()
    gateway = MagicMock()
    gateway.type = "Gateway"
    gateway.identifier = "gateway123"
    gateway.name = "Gateway"
    gateway.has_attribute.return_value = False
    hilo.devices = MagicMock(all=[gateway])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hilo

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    with (
        patch.object(hilo, "check_season", return_value=is_winter),
        patch(
            "custom_components.hilo.sensor.EnergyManager.init",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.hilo.sensor.UtilityManager.update",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.hilo.sensor.EnergyManager.update",
            new_callable=AsyncMock,
        ),
    ):
        await async_setup_entry(hass, entry, mock_add_entities)

    assert hilo.cost_sensors["low"]._cost == expected_low
    assert hilo.cost_sensors["medium"]._cost == expected_med
    assert hilo.cost_sensors["high"]._cost == expected_high
    assert hilo.cost_sensors["current"]._cost == expected_low


def test_hilo_cost_total_sensor_tariff_config():
    """Test HiloCostTotalSensor delegates tariff_config to Hilo."""
    hilo = Hilo.__new__(Hilo)
    hilo.hq_plan_name = "flex d"
    sensor = HiloCostTotalSensor.__new__(HiloCostTotalSensor)
    sensor._hilo = hilo

    with patch.object(hilo, "check_season", return_value=False):
        assert sensor.tariff_config == hilo.get_tariff_config()
