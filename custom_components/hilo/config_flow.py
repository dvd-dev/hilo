"""Config flow to configure the Hilo component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from awesomeversion import AwesomeVersion
from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, __version__ as HAVERSION
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, selector
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2FlowHandler
from homeassistant.util import slugify
import jwt
import voluptuous as vol

from .const import (
    CONF_ACCOUNT_LABEL,
    CONF_APPRECIATION_PHASE,
    CONF_CHALLENGE_LOCK,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_LOG_TRACES,
    CONF_PRE_COLD_PHASE,
    CONF_TARIFF,
    CONF_TRACK_UNKNOWN_SOURCES,
    CONF_UNTARIFICATED_DEVICES,
    DEFAULT_APPRECIATION_PHASE,
    DEFAULT_CHALLENGE_LOCK,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_LOG_TRACES,
    DEFAULT_PRE_COLD_PHASE,
    DEFAULT_TRACK_UNKNOWN_SOURCES,
    DEFAULT_UNTARIFICATED_DEVICES,
    DOMAIN,
    LOG,
    MIN_SCAN_INTERVAL,
)
from .oauth2 import AuthCodeWithPKCEImplementation

STEP_OPTION_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_GENERATE_ENERGY_METERS, default=DEFAULT_GENERATE_ENERGY_METERS
        ): cv.boolean,
        vol.Optional(
            CONF_UNTARIFICATED_DEVICES,
            default=DEFAULT_UNTARIFICATED_DEVICES,
        ): cv.boolean,
        vol.Optional(
            CONF_LOG_TRACES,
            default=DEFAULT_LOG_TRACES,
        ): cv.boolean,
        vol.Optional(
            CONF_CHALLENGE_LOCK,
            default=DEFAULT_CHALLENGE_LOCK,
        ): cv.boolean,
        vol.Optional(
            CONF_TRACK_UNKNOWN_SOURCES,
            default=DEFAULT_TRACK_UNKNOWN_SOURCES,
        ): cv.boolean,
        vol.Optional(
            CONF_HQ_PLAN_NAME, default=DEFAULT_HQ_PLAN_NAME
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(options=list(CONF_TARIFF.keys()), mode="list")
        ),
        vol.Optional(
            CONF_APPRECIATION_PHASE,
            default=DEFAULT_APPRECIATION_PHASE,
        ): cv.positive_int,
        vol.Optional(
            CONF_PRE_COLD_PHASE,
            default=DEFAULT_PRE_COLD_PHASE,
        ): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL): (
            vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL))
        ),
    }
)


def account_email(access_token: str) -> str:
    """Return the email identifying the Hilo account that owns the token."""
    claims = jwt.decode(access_token, options={"verify_signature": False})
    return str(claims["email"]).lower()


class HiloFlowHandler(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """Handle a Hilo config flow."""

    DOMAIN = DOMAIN
    VERSION = 2
    MINOR_VERSION = 2

    _email: str
    _oauth_data: dict

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle a flow initialized by the user."""
        self.async_register_implementation(
            self.hass,
            AuthCodeWithPKCEImplementation(self.hass),
        )

        return await super().async_step_user(user_input)

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return LOG

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HiloOptionsFlowHandler:
        """Define the config flow to handle options."""
        return HiloOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data: Mapping[str, object]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        self.async_register_implementation(
            self.hass,
            AuthCodeWithPKCEImplementation(self.hass),
        )
        user_input["implementation"] = DOMAIN
        return await super().async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        email = account_email(data["token"]["access_token"])
        await self.async_set_unique_id(email)

        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            # Entries migrated from version 1 have no token to tell which
            # account they belong to, so their first reauth claims one.
            if reauth_entry.unique_id == DOMAIN:
                self._abort_if_unique_id_configured()
            else:
                self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                reauth_entry, unique_id=email, data_updates=data
            )

        self._abort_if_unique_id_configured()
        self._email = email
        self._oauth_data = data
        # One account keeps unprefixed names, so that an account set up before
        # multi-account support, or added back after being removed, keeps its
        # entity_ids, dashboards and energy statistics.
        if "" not in self._taken_labels():
            return self._async_create_account_entry("")
        return await self.async_step_account_label()

    async def async_step_account_label(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Name an additional account, which prefixes its entity names."""
        errors: dict[str, str] = {}
        if user_input is not None:
            label = user_input[CONF_ACCOUNT_LABEL].strip()
            if not any(char.isalnum() for char in label):
                errors[CONF_ACCOUNT_LABEL] = "invalid_account_label"
            elif slugify(label) in self._taken_labels():
                errors[CONF_ACCOUNT_LABEL] = "account_label_taken"
            else:
                return self._async_create_account_entry(label)

        return self.async_show_form(
            step_id="account_label",
            data_schema=vol.Schema(
                {vol.Required(CONF_ACCOUNT_LABEL, default=self._suggested_label()): str}
            ),
            errors=errors,
        )

    @callback
    def _async_create_account_entry(self, label: str) -> FlowResult:
        """Create the entry of a newly added account."""
        return self.async_create_entry(
            title=self._email,
            data={**self._oauth_data, CONF_ACCOUNT_LABEL: label},
        )

    def _taken_labels(self) -> set[str]:
        """Return the slugs of the labels used by configured accounts."""
        return {
            slugify(entry.data.get(CONF_ACCOUNT_LABEL, ""))
            for entry in self._async_current_entries()
        }

    def _suggested_label(self) -> str:
        """Suggest a free label derived from the account email."""
        taken = self._taken_labels()
        base = self._email.split("@")[0]
        label = base
        suffix = 2
        while slugify(label) in taken:
            label = f"{base} {suffix}"
            suffix += 1
        return label


class HiloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Hilo options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        if AwesomeVersion(HAVERSION) < "2024.11.99":
            self.config_entry = config_entry
        else:
            self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_OPTION_SCHEMA, self.config_entry.options
            ),
        )
