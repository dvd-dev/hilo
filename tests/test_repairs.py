"""Tests for Hilo deprecation repair issues and fix flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.repairs import ConfirmRepairFlow, repairs_flow_manager
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hilo.const import (
    CONF_GENERATE_ENERGY_METERS,
    CONF_TRACK_UNKNOWN_SOURCES,
    DOMAIN,
    ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER,
    UNKNOWN_SOURCE_TRACKER_IDENTIFIER,
    UNKNOWN_SOURCE_TRACKER_UTILITY_METER,
)
from custom_components.hilo.repairs import async_create_fix_flow

from . import patch_hilo_setup, setup_with_selected_platforms

TRACKER_POWER_ENTITY = "sensor.unknown_source_tracker_power"
TRACKER_POWER_UID = f"{UNKNOWN_SOURCE_TRACKER_IDENTIFIER}-power"
TRACKER_ENERGY_UID = f"{UNKNOWN_SOURCE_TRACKER_IDENTIFIER}-energy"


def _issue_id(entry: MockConfigEntry) -> str:
    return f"{ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER}_{entry.entry_id}"


def _enable_tracker(
    hass: HomeAssistant, entry: MockConfigEntry, **extra_options: bool
) -> None:
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={CONF_TRACK_UNKNOWN_SOURCES: True, **extra_options}
    )


async def _setup_automation(
    hass: HomeAssistant,
    *,
    alias: str,
    auto_id: str | None = None,
    entity_id: str | None = None,
    device_id: str | None = None,
) -> None:
    config: dict[str, object] = {
        "alias": alias,
        "trigger": (
            {"platform": "state", "entity_id": entity_id}
            if entity_id
            else {"platform": "homeassistant", "event": "start"}
        ),
        "action": (
            {"action": "test.noop", "target": {"device_id": device_id}}
            if device_id
            else {"delay": 1}
        ),
    }
    if auto_id is not None:
        config["id"] = auto_id
    assert await async_setup_component(hass, "automation", {"automation": [config]})


def _assert_used_issue(issue_registry: ir.IssueRegistry, entry: MockConfigEntry) -> str:
    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(entry))
    assert issue is not None
    assert issue.translation_key == f"{ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER}_used"
    assert issue.translation_placeholders is not None
    return issue.translation_placeholders["items"]


async def test_no_issue_when_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Clear any stale issue and create none when the option is disabled."""
    stale_issue_id = _issue_id(mock_config_entry)
    ir.async_create_issue(
        hass,
        DOMAIN,
        stale_issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER,
    )
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    assert issue_registry.async_get_issue(DOMAIN, stale_issue_id) is None


async def test_issue_created_when_enabled_without_references(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Create a fixable warning issue when enabled with no references."""
    _enable_tracker(hass, mock_config_entry)
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )

    issue = issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry))
    assert issue is not None
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.is_fixable is True
    assert issue.is_persistent is False
    assert issue.breaks_in_ha_version is None
    assert issue.translation_key == ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER
    assert issue.translation_placeholders is None


@pytest.mark.parametrize(
    ("component", "config", "expected_item"),
    [
        pytest.param(
            "automation",
            {
                "automation": [
                    {
                        "id": "tracker_entity_auto",
                        "alias": "Tracker Entity Auto",
                        "trigger": {
                            "platform": "state",
                            "entity_id": TRACKER_POWER_ENTITY,
                        },
                        "action": {"delay": 1},
                    }
                ]
            },
            "- [Tracker Entity Auto](/config/automation/edit/tracker_entity_auto)",
            id="automation_with_id",
        ),
        pytest.param(
            "automation",
            {
                "automation": [
                    {
                        "alias": "YAML Tracker Auto",
                        "trigger": {
                            "platform": "state",
                            "entity_id": TRACKER_POWER_ENTITY,
                        },
                        "action": {"delay": 1},
                    }
                ]
            },
            "- `automation.yaml_tracker_auto`",
            id="automation_without_id",
        ),
        pytest.param(
            "script",
            {
                "script": {
                    "tracker_utility_script": {
                        "alias": "Tracker Utility Script",
                        "sequence": [
                            {
                                "action": "test.noop",
                                "target": {
                                    "entity_id": (
                                        f"sensor.{UNKNOWN_SOURCE_TRACKER_UTILITY_METER}_low"
                                    )
                                },
                            }
                        ],
                    }
                }
            },
            "- [Tracker Utility Script](/config/script/edit/tracker_utility_script)",
            id="script_referencing_utility_meter",
        ),
    ],
)
async def test_issue_lists_entity_references(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
    component: str,
    config: dict[str, object],
    expected_item: str,
) -> None:
    """List automations and scripts referencing tracker or utility meter entities."""
    _enable_tracker(hass, mock_config_entry)
    assert await async_setup_component(hass, component, config)
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    assert expected_item in _assert_used_issue(issue_registry, mock_config_entry)


async def test_issue_detects_renamed_tracker_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Detect references to a renamed Unknown Source Tracker entity."""
    _enable_tracker(hass, mock_config_entry)
    entity_registry.async_get_or_create(
        Platform.SENSOR,
        DOMAIN,
        TRACKER_POWER_UID,
        config_entry=mock_config_entry,
        suggested_object_id="custom_other_power",
    )
    await _setup_automation(
        hass,
        alias="Renamed Tracker Auto",
        auto_id="renamed_tracker_auto",
        entity_id="sensor.custom_other_power",
    )
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    assert (
        "- [Renamed Tracker Auto](/config/automation/edit/renamed_tracker_auto)"
        in _assert_used_issue(issue_registry, mock_config_entry)
    )


async def test_issue_lists_device_references(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Include automations and scripts targeting the tracker device ID."""
    _enable_tracker(hass, mock_config_entry)
    tracker_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, UNKNOWN_SOURCE_TRACKER_IDENTIFIER)},
    )
    await _setup_automation(
        hass,
        alias="Tracker Device Auto",
        auto_id="dev_auto",
        device_id=tracker_device.id,
    )
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "dev_script": {
                    "alias": "Tracker Device Script",
                    "sequence": [
                        {
                            "action": "test.noop",
                            "target": {"device_id": tracker_device.id},
                        }
                    ],
                }
            }
        },
    )
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    items = _assert_used_issue(issue_registry, mock_config_entry)
    assert "- [Tracker Device Auto](/config/automation/edit/dev_auto)" in items
    assert "- [Tracker Device Script](/config/script/edit/dev_script)" in items


async def test_issue_deferred_until_hass_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Defer deprecation scan on startup until Home Assistant has started."""
    hass.set_state(CoreState.not_running)
    _enable_tracker(hass, mock_config_entry)
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    assert issue_registry.async_get_issue(DOMAIN, _issue_id(mock_config_entry)) is None

    await _setup_automation(
        hass,
        alias="Startup Deferred Auto",
        auto_id="startup_deferred_auto",
        entity_id=TRACKER_POWER_ENTITY,
    )
    await hass.async_start()
    await hass.async_block_till_done()
    assert (
        "- [Startup Deferred Auto](/config/automation/edit/startup_deferred_auto)"
        in _assert_used_issue(issue_registry, mock_config_entry)
    )


async def test_fix_flow_disables_option_removes_entries_and_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Submitting the repair flow disables the option, removes entries, and reloads."""
    assert await async_setup_component(hass, "repairs", {})
    _enable_tracker(hass, mock_config_entry, **{CONF_GENERATE_ENERGY_METERS: True})
    await _setup_automation(
        hass,
        alias="Fix Flow Auto",
        auto_id="fix_flow_auto",
        entity_id=TRACKER_POWER_ENTITY,
    )

    with (
        patch_hilo_setup([Platform.SENSOR], mock_api),
        patch(
            "custom_components.hilo.sensor.UtilityManager.update",
            new_callable=AsyncMock,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        issue_id = _issue_id(mock_config_entry)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None
        for uid in (TRACKER_POWER_UID, TRACKER_ENERGY_UID):
            assert entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, uid)

        flow_manager = repairs_flow_manager(hass)
        assert flow_manager is not None
        result = await flow_manager.async_init(
            DOMAIN, context={"issue_id": issue_id}, data={"issue_id": issue_id}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
        assert (
            "- [Fix Flow Auto](/config/automation/edit/fix_flow_auto)"
            in result["description_placeholders"]["items"]
        )

        result = await flow_manager.async_configure(result["flow_id"], user_input={})
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.track_unknown_sources is False
    assert mock_config_entry.options[CONF_TRACK_UNKNOWN_SOURCES] is False
    assert mock_config_entry.options[CONF_GENERATE_ENERGY_METERS] is True
    for uid in (TRACKER_POWER_UID, TRACKER_ENERGY_UID):
        assert entity_registry.async_get_entity_id(Platform.SENSOR, DOMAIN, uid) is None
    assert not any(
        (DOMAIN, UNKNOWN_SOURCE_TRACKER_IDENTIFIER) in device.identifiers
        for device in dr.async_entries_for_config_entry(
            device_registry, mock_config_entry.entry_id
        )
    )
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_unload_preserves_issue_and_remove_deletes_issue(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
    mock_api: MagicMock,
) -> None:
    """Unloading keeps the repair issue while entry removal deletes it."""
    _enable_tracker(hass, mock_config_entry)
    await setup_with_selected_platforms(
        hass, mock_config_entry, [Platform.SENSOR], mock_api
    )
    issue_id = _issue_id(mock_config_entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_create_fix_flow_unknown_issue_returns_confirm_flow(
    hass: HomeAssistant,
) -> None:
    """Fall back to ConfirmRepairFlow for unrecognized issue IDs."""
    assert isinstance(
        await async_create_fix_flow(hass, "other", None), ConfirmRepairFlow
    )
