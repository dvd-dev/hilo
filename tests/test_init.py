"""Test component setup."""

from pathlib import Path
from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hilo.const import (
    ACCOUNT_FILES,
    CONF_ACCOUNT_LABEL,
    CONF_TRACK_UNKNOWN_SOURCES,
    DOMAIN,
)

from . import ACCOUNT_EMAIL, oauth_token, setup_with_selected_platforms


async def test_async_setup(hass):
    """Test the component gets setup."""
    assert await async_setup_component(hass, DOMAIN, {}) is True


def legacy_entry() -> MockConfigEntry:
    """Return an entry created while only a single account was supported."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, "token": oauth_token(ACCOUNT_EMAIL)},
        unique_id=DOMAIN,
        version=2,
        minor_version=1,
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_migration_identifies_account(hass: HomeAssistant) -> None:
    """Test a single-account entry is keyed by its account and keeps its names."""
    entry = legacy_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.minor_version == 2
    assert entry.unique_id == ACCOUNT_EMAIL
    assert entry.data[CONF_ACCOUNT_LABEL] == ""


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("legacy_file", "account_file"),
    [
        pytest.param("hilo_state.yaml", "hilo_state_{}.yaml", id="api_state"),
        pytest.param(
            "hilo_eventhistory_state.yaml",
            "hilo_eventhistory_state_{}.yaml",
            id="event_history",
        ),
    ],
)
async def test_migration_hands_files_to_entry(
    hass: HomeAssistant, tmp_path: Path, legacy_file: str, account_file: str
) -> None:
    """Test the single-account files become the migrated entry's files."""
    hass.config.config_dir = str(tmp_path)
    (tmp_path / legacy_file).write_text("legacy: true\n")
    entry = legacy_entry()
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert not (tmp_path / legacy_file).exists()
    assert (tmp_path / account_file.format(entry.entry_id)).read_text() == (
        "legacy: true\n"
    )


@pytest.mark.usefixtures("mock_setup_entry")
async def test_remove_entry_deletes_account_files(
    hass: HomeAssistant, tmp_path: Path, mock_config_entry: MockConfigEntry
) -> None:
    """Test removing an account deletes only that account's files."""
    hass.config.config_dir = str(tmp_path)
    mock_config_entry.add_to_hass(hass)
    for account_file in ACCOUNT_FILES.values():
        (tmp_path / account_file.format(mock_config_entry.entry_id)).touch()
        (tmp_path / account_file.format("other_entry")).touch()

    await hass.config_entries.async_remove(mock_config_entry.entry_id)

    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(
        account_file.format("other_entry") for account_file in ACCOUNT_FILES.values()
    )


@pytest.mark.parametrize(
    ("identifier", "expected_success"),
    [
        pytest.param("2a3b4c5d6e7f", False, id="device_still_reported"),
        pytest.param("stale-device", True, id="device_no_longer_reported"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_api: MagicMock,
    identifier: str,
    expected_success: bool,
) -> None:
    """Test only devices no longer reported by Hilo can be removed."""
    assert await async_setup_component(hass, "config", {})
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SWITCH], mock_api
    )
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, identifier)},
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mock_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()

    assert response["success"] is expected_success
    assert (device_registry.async_get(device_entry.id) is None) is expected_success


async def test_remove_config_entry_device_unknown_source_tracker(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_api: MagicMock,
) -> None:
    """Test the unknown source tracker device cannot be removed while tracked."""
    assert await async_setup_component(hass, "config", {})
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_TRACK_UNKNOWN_SOURCES: True}
    )
    await setup_with_selected_platforms(hass, mock_config_entry, [], mock_api)
    device_entry = next(
        device
        for device in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
        if (DOMAIN, "hass-hilo-unknown_source_tracker") in device.identifiers
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mock_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await client.receive_json()

    assert response["success"] is False
    assert device_registry.async_get(device_entry.id) is not None
