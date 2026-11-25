"""Repairs for the Hilo integration."""

from __future__ import annotations

from homeassistant.components.automation import (
    automations_with_device,
    automations_with_entity,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.components.script import scripts_with_device, scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import voluptuous as vol

from .const import (
    CONF_TRACK_UNKNOWN_SOURCES,
    DEFAULT_TRACK_UNKNOWN_SOURCES,
    DOMAIN,
    ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER,
    LOG,
    TARIFF_LIST,
    UNKNOWN_SOURCE_TRACKER_IDENTIFIER,
    UNKNOWN_SOURCE_TRACKER_UTILITY_METER,
)


def _issue_id(entry_id: str) -> str:
    """Return the repair issue ID for the deprecated Unknown Source Tracker."""
    return f"{ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER}_{entry_id}"


def _get_tracker_device_and_entities(
    hass: HomeAssistant, entry_id: str
) -> tuple[dr.DeviceEntry | None, list[er.RegistryEntry]]:
    """Return the Unknown Source Tracker device entry and its Hilo entity entries."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    device_entry = next(
        (
            device
            for device in dr.async_entries_for_config_entry(device_registry, entry_id)
            if (DOMAIN, UNKNOWN_SOURCE_TRACKER_IDENTIFIER) in device.identifiers
        ),
        None,
    )
    if device_entry is None:
        return None, []
    entities = [
        entity_entry
        for entity_entry in er.async_entries_for_device(
            entity_registry, device_entry.id, include_disabled_entities=True
        )
        if entity_entry.platform == DOMAIN
    ]
    return device_entry, entities


def _get_referencing_items(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_entry: dr.DeviceEntry | None,
    entity_ids: set[str],
) -> list[str]:
    """Return markdown list items for automations and scripts referencing tracker."""
    items: list[str] = []
    for domain_name, entity_lookup, device_lookup in (
        ("automation", automations_with_entity, automations_with_device),
        ("script", scripts_with_entity, scripts_with_device),
    ):
        matched_ids = {
            ref_id
            for entity_id in entity_ids
            for ref_id in entity_lookup(hass, entity_id)
        }
        if device_entry is not None:
            matched_ids.update(device_lookup(hass, device_entry.id))
        for ref_entity_id in sorted(matched_ids):
            if (
                reg_entry := entity_registry.async_get(ref_entity_id)
            ) and reg_entry.unique_id:
                label = reg_entry.name or reg_entry.original_name or ref_entity_id
                items.append(
                    f"- [{label}](/config/{domain_name}/edit/{reg_entry.unique_id})"
                )
            else:
                items.append(f"- `{ref_entity_id}`")
    return items


@callback
def async_manage_unknown_source_tracker_deprecation_issue(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Create, update, or clear the Unknown Source Tracker deprecation issue."""
    issue_id = _issue_id(entry.entry_id)
    if not entry.options.get(CONF_TRACK_UNKNOWN_SOURCES, DEFAULT_TRACK_UNKNOWN_SOURCES):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    LOG.warning(
        "The 'Track unknown power sources' option is deprecated and will be "
        "removed in a future release; use Home Assistant's Energy dashboard "
        "untracked consumption or a Template sensor instead"
    )

    device_entry, hilo_entities = _get_tracker_device_and_entities(hass, entry.entry_id)
    tracked_entity_ids = (
        {entity.entity_id for entity in hilo_entities}
        | {
            f"sensor.{UNKNOWN_SOURCE_TRACKER_UTILITY_METER}_{tariff}"
            for tariff in (*TARIFF_LIST, "total")
        }
        | {f"select.{UNKNOWN_SOURCE_TRACKER_UTILITY_METER}"}
    )
    items = _get_referencing_items(
        hass, er.async_get(hass), device_entry, tracked_entity_ids
    )

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data={"entry_id": entry.entry_id},
        is_fixable=True,
        is_persistent=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=(
            f"{ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER}_used"
            if items
            else ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER
        ),
        translation_placeholders={"items": "\n".join(items)} if items else None,
    )


@callback
def async_delete_unknown_source_tracker_deprecation_issue(
    hass: HomeAssistant, entry_id: str
) -> None:
    """Delete the Unknown Source Tracker deprecation issue for a config entry."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(entry_id))


class DeprecatedUnknownSourceTrackerRepairFlow(RepairsFlow):
    """Handler for fixing the deprecated Unknown Source Tracker issue."""

    def __init__(self, entry_id: str) -> None:
        """Initialize the repair flow."""
        super().__init__()
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm disabling the Unknown Source Tracker and removing its entities."""
        if user_input is not None:
            # Remove registry entries before updating options so reload sees none left.
            device_entry, hilo_entities = _get_tracker_device_and_entities(
                self.hass, self._entry_id
            )
            entity_registry = er.async_get(self.hass)
            for entity_entry in hilo_entities:
                entity_registry.async_remove(entity_entry.entity_id)
            if device_entry is not None:
                dr.async_get(self.hass).async_remove_device(device_entry.id)

            if entry := self.hass.config_entries.async_get_entry(self._entry_id):
                self.hass.config_entries.async_update_entry(
                    entry, options={**entry.options, CONF_TRACK_UNKNOWN_SOURCES: False}
                )
            return self.async_create_entry(data={})

        issue = ir.async_get(self.hass).async_get_issue(self.handler, self.issue_id)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=issue.translation_placeholders if issue else None,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair fix flow for Hilo issues."""
    if (
        issue_id.startswith(f"{ISSUE_DEPRECATED_UNKNOWN_SOURCE_TRACKER}_")
        and data
        and isinstance(entry_id := data.get("entry_id"), str)
    ):
        return DeprecatedUnknownSourceTrackerRepairFlow(entry_id)
    return ConfirmRepairFlow()
