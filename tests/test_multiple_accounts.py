"""Tests for running several Hilo accounts side by side."""

from unittest.mock import MagicMock

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from custom_components.hilo import Hilo
from custom_components.hilo.const import (
    CONF_ACCOUNT_LABEL,
    CONF_GENERATE_ENERGY_METERS,
    DOMAIN,
)

from . import ACCOUNT_EMAIL, oauth_token, setup_with_selected_platforms

SECOND_EMAIL = "second.account@example.com"


def account_entry(email: str, label: str, options: dict[str, bool]) -> MockConfigEntry:
    """Return a config entry for a Hilo account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=email,
        data={
            "auth_implementation": DOMAIN,
            "token": oauth_token(email),
            CONF_ACCOUNT_LABEL: label,
        },
        options=options,
        unique_id=email,
        version=2,
        minor_version=2,
    )


async def setup_two_accounts(
    hass: HomeAssistant,
    platforms: list[Platform],
    mock_api: MagicMock,
    second_account_api: MagicMock,
    options: dict[str, bool],
) -> MockConfigEntry:
    """Set up two accounts whose devices share names, return the second one."""
    first = account_entry(ACCOUNT_EMAIL, "", options)
    second = account_entry(SECOND_EMAIL, "second.account", options)
    await setup_with_selected_platforms(hass, first, platforms, mock_api)
    await setup_with_selected_platforms(hass, second, platforms, second_account_api)
    return second


async def test_second_account_entities_are_prefixed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_api: MagicMock,
    second_account_api: MagicMock,
) -> None:
    """Test devices named like the first account's get distinct entities."""
    second = await setup_two_accounts(
        hass, [Platform.SWITCH], mock_api, second_account_api, {}
    )

    await snapshot_platform(hass, entity_registry, snapshot, second.entry_id)


@pytest.mark.parametrize(
    "meter_entity_id",
    [
        pytest.param("sensor.hilo_energy_total_low", id="first_account"),
        pytest.param(
            "sensor.second_account_hilo_energy_total_low", id="second_account"
        ),
    ],
)
async def test_each_account_gets_its_own_energy_meters(
    hass: HomeAssistant,
    mock_api: MagicMock,
    second_account_api: MagicMock,
    meter_entity_id: str,
) -> None:
    """Test generated utility meters of both accounts coexist."""
    # Home Assistant loads it before Hilo through after_dependencies.
    assert await async_setup_component(hass, "utility_meter", {})
    await setup_two_accounts(
        hass,
        [Platform.SENSOR],
        mock_api,
        second_account_api,
        {CONF_GENERATE_ENERGY_METERS: True},
    )

    assert hass.states.get(meter_entity_id) is not None


async def test_accounts_do_not_set_up_each_others_meters(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_api: MagicMock,
    second_account_api: MagicMock,
) -> None:
    """Test adding an account leaves the existing utility meters alone."""
    assert await async_setup_component(hass, "utility_meter", {})

    await setup_two_accounts(
        hass,
        [Platform.SENSOR],
        mock_api,
        second_account_api,
        {CONF_GENERATE_ENERGY_METERS: True},
    )

    assert "Entity id already exists" not in caplog.text


def power_device(
    device_type: str, power: int | None, available: bool = True, model: str = "X"
) -> MagicMock:
    """Return a device reporting the given power."""
    device = MagicMock(type=device_type, available=available, model=model)
    device.has_attribute.side_effect = lambda attribute: attribute == "power"
    device.get_value.return_value = power
    return device


def account_hilo(hass: HomeAssistant, entry: MockConfigEntry, label: str) -> Hilo:
    """Return a Hilo account object without connecting to the API."""
    hilo = Hilo.__new__(Hilo)
    hilo._hass = hass
    hilo.entry = entry
    hilo.name_prefix = f"{label} "
    hilo.hq_plan_name = "rate d"
    hilo.generate_energy_meters = True
    hilo.untarificated_devices = False
    hilo.cost_sensors = {}
    hilo.challenge_sensor = None
    return hilo


async def test_check_tarif_only_switches_own_meters(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an account never changes the tariff of another account's meters."""
    hilo = account_hilo(hass, mock_config_entry, "second.account")
    hilo.energy_meter_keys = ["second_account_hilo_energy_total"]
    hass.states.async_set("select.second_account_hilo_energy_total", "medium")
    hass.states.async_set("select.hilo_energy_total", "medium")
    calls = async_mock_service(hass, SELECT_DOMAIN, SERVICE_SELECT_OPTION)

    hilo.check_tarif()
    await hass.async_block_till_done()

    assert [call.data["entity_id"] for call in calls] == [
        "select.second_account_hilo_energy_total"
    ]


@pytest.mark.parametrize(
    "ignored_device",
    [
        pytest.param(
            power_device("Thermostat", 900, available=False), id="unavailable"
        ),
        pytest.param(
            power_device("Thermostat", 900, model="TH6250WF"), id="unmonitored"
        ),
        pytest.param(power_device("Thermostat", None), id="no_reading_value"),
    ],
)
def test_unknown_power_uses_own_devices(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, ignored_device: MagicMock
) -> None:
    """Test unknown power is the smart meter minus the account's own devices."""
    hilo = account_hilo(hass, mock_config_entry, "second.account")
    hilo.unknown_tracker_device = power_device("Tracker", 77)
    hilo.devices = MagicMock(
        all=[
            power_device("Meter", 5000),
            power_device("Outlet", 1200),
            ignored_device,
            hilo.unknown_tracker_device,
        ]
    )

    hilo.handle_unknown_power()

    [readings] = hilo.devices.parse_values_received.call_args.args
    assert readings[0]["value"] == 3800


async def test_legacy_gateway_lookup_ignores_other_accounts(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test another account's gateway is never mistaken for a legacy DSN."""
    other_entry = account_entry(SECOND_EMAIL, "second.account", {})
    other_entry.add_to_hass(hass)
    mock_config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "aa:bb:cc:dd:ee:ff")},
        manufacturer="Hilo",
        model="EQ000017",
    )
    hilo = account_hilo(hass, mock_config_entry, "")

    assert await hilo._fetch_legacy_gateway_dsn("11:22:33:44:55:66") is None
