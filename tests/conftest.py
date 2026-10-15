"""Fixtures for testing."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pyhilo.api import API as RealAPI
from pyhilo.device import get_device_attributes
from pyhilo.signalr import SignalRHub
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_fixture,
)
from pytest_homeassistant_custom_component.syrupy import (
    HomeAssistantSnapshotExtension,
    HomeAssistantSnapshotSerializer,
)
from syrupy.assertion import SnapshotAssertion
from syrupy.types import SerializableData

from custom_components.hilo.const import DOMAIN


class CrossVersionSnapshotSerializer(HomeAssistantSnapshotSerializer):
    """Normalize internal HA data structures across Python 3.13 and 3.14 (HA 2026.3+)."""

    @classmethod
    def _serializable_state(cls, data: State) -> SerializableData:
        serialized = super()._serializable_state(data)
        if "attributes" in serialized and isinstance(serialized["attributes"], dict):
            serialized["attributes"] = {
                str(k): v for k, v in serialized["attributes"].items()
            }
        return serialized

    @classmethod
    def _serializable_entity_registry_entry(
        cls, data: er.RegistryEntry
    ) -> SerializableData:
        serialized = super()._serializable_entity_registry_entry(data)
        if "aliases" in serialized:
            aliases = serialized["aliases"]
            if aliases is None:
                serialized["aliases"] = []
            elif isinstance(aliases, (set, list)):
                serialized["aliases"] = sorted(str(a) for a in aliases if a is not None)
        if "capabilities" in serialized and isinstance(
            serialized["capabilities"], dict
        ):
            serialized["capabilities"] = {
                str(k): v for k, v in serialized["capabilities"].items()
            }
        return serialized


class CrossVersionSnapshotExtension(HomeAssistantSnapshotExtension):
    """Snapshot extension with cross-version normalization."""

    serializer_class = CrossVersionSnapshotSerializer


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return snapshot assertion fixture with cross-version compatibility."""
    return snapshot.use_extension(CrossVersionSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def entity_registry_enabled_by_default() -> Generator[None]:
    """Test fixture that ensures all entities are enabled in the registry."""
    with patch(
        "homeassistant.helpers.entity.Entity.entity_registry_enabled_default",
        return_value=True,
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": "hilo", "token": "123"},
        unique_id="hilo",
        version=2,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "custom_components.hilo.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_onboarding() -> Generator[MagicMock]:
    """Mock that Home Assistant is currently onboarding."""
    with patch(
        "homeassistant.components.onboarding.async_is_onboarded",
        return_value=False,
    ) as mock_onboarding:
        yield mock_onboarding


@pytest.fixture
def mock_api() -> Generator[MagicMock]:
    """Return a mocked Hilo API"""
    with patch("pyhilo.API", autospec=True) as api_mock:
        # Mock SignalR hubs to prevent indefinite blocking
        api_mock.signalr_devices = AsyncMock(spec=SignalRHub)
        api_mock.signalr_devices.run = AsyncMock(return_value=None)
        api_mock.signalr_devices.connected = False
        api_mock.signalr_devices.disconnect = AsyncMock(return_value=None)
        api_mock.signalr_challenges = AsyncMock(spec=SignalRHub)
        api_mock.signalr_challenges.run = AsyncMock(return_value=None)
        api_mock.signalr_challenges.connected = False
        api_mock.signalr_challenges.disconnect = AsyncMock(return_value=None)

        all_devices = json.loads(load_fixture("all_devices.json"))

        api_mock.log_traces = True
        api_mock.wait_for_device_cache = AsyncMock(return_value=None)
        api_mock.get_device_cache.return_value = all_devices
        api_mock.get_location_ids = AsyncMock(return_value=(123, "urn:test:hilo:id"))
        api_mock.get_gateway = AsyncMock(
            return_value=next(d for d in all_devices if d.get("type") == "Gateway")
        )
        dev_atts_fn = RealAPI.dev_atts
        api_mock.device_attributes = get_device_attributes()
        api_mock.dev_atts.side_effect = lambda attr, val_type=None: dev_atts_fn(
            api_mock, attr, val_type
        )
        api_mock._set_device_attribute = AsyncMock()
        api_mock._get_device_callbacks = []
        api_mock.async_create.return_value = api_mock
        yield api_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> MockConfigEntry:
    """Set up the Hilo integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch("custom_components.hilo.API.async_create", return_value=mock_api),
        patch(
            "custom_components.hilo.Hilo.should_signalr_reconnect",
            new_callable=PropertyMock,
        ) as mock_should_signalr_reconnect,
    ):
        mock_should_signalr_reconnect.return_value = False
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry
