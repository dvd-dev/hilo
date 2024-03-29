"""Config flow to configure the Hilo component."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.typing import ConfigType
from pyhilo import API
from pyhilo.exceptions import HiloError, InvalidCredentialsError
import voluptuous as vol

from .const import (
    CONF_APPRECIATION_PHASE,
    CONF_CHALLENGE_LOCK,
    CONF_GENERATE_ENERGY_METERS,
    CONF_HQ_PLAN_NAME,
    CONF_LOG_TRACES,
    CONF_PRE_COLD_PHASE,
    CONF_TRACK_UNKNOWN_SOURCES,
    CONF_UNTARIFICATED_DEVICES,
    DEFAULT_APPRECIATION_PHASE,
    DEFAULT_CHALLENGE_LOCK,
    DEFAULT_GENERATE_ENERGY_METERS,
    DEFAULT_HQ_PLAN_NAME,
    DEFAULT_LOG_TRACES,
    DEFAULT_PRE_COLD_PHASE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRACK_UNKNOWN_SOURCES,
    DEFAULT_UNTARIFICATED_DEVICES,
    DOMAIN,
    LOG,
    MIN_SCAN_INTERVAL,
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)
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
            CONF_APPRECIATION_PHASE,
            default=DEFAULT_APPRECIATION_PHASE,
        ): cv.positive_int,
        vol.Optional(
            CONF_PRE_COLD_PHASE,
            default=DEFAULT_PRE_COLD_PHASE,
        ): cv.positive_int,
        vol.Optional(CONF_HQ_PLAN_NAME, default=DEFAULT_HQ_PLAN_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): (
            vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL))
        ),
    }
)


class HiloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Hilo config flow."""

    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, Any] = {}
        self._reauth: bool = False
        self._username: str | None = None
        self._password: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HiloOptionsFlowHandler:
        """Define the config flow to handle options."""
        return HiloOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, config: ConfigType) -> FlowResult:
        """Handle configuration by re-auth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self._async_show_form(
                step_id="reauth_confirm",
            )
        return await self.async_step_user(user_input)

    async def async_oauth_create_entry(self, data: dict) -> dict:
        """Create an oauth config entry or update existing entry for reauth."""
        if self.reauth_entry:
            self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
            await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")
        await self.async_set_unique_id(data["username"])
        self._abort_if_unique_id_configured()
        LOG.debug(f"Creating entry: {data}")
        return self.async_create_entry(title=data["username"], data=data)

    def _async_show_form(
        self, *, step_id: str = "user", errors: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show the form."""
        return self.async_show_form(
            step_id=step_id,
            data_schema=STEP_USER_SCHEMA,
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self._async_show_form()
        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            hilo = await API.async_auth_password(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=session,
            )
        except InvalidCredentialsError:
            errors = {"base": "invalid_auth"}
        except HiloError as err:
            LOG.error("Unknown error while logging into Hilo: %s", err)
            errors = {"base": "unknown"}

        if errors:
            return self._async_show_form(errors=errors)

        data = {CONF_USERNAME: hilo._username, CONF_TOKEN: hilo._refresh_token}
        return await self.async_oauth_create_entry(data)


class HiloOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a Hilo options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_GENERATE_ENERGY_METERS,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_GENERATE_ENERGY_METERS
                            )
                        },
                    ): cv.boolean,
                    vol.Optional(
                        CONF_UNTARIFICATED_DEVICES,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_UNTARIFICATED_DEVICES
                            )
                        },
                    ): cv.boolean,
                    vol.Optional(
                        CONF_LOG_TRACES,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_LOG_TRACES
                            )
                        },
                    ): cv.boolean,
                    vol.Optional(
                        CONF_CHALLENGE_LOCK,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_CHALLENGE_LOCK
                            )
                        },
                    ): cv.boolean,
                    vol.Optional(
                        CONF_TRACK_UNKNOWN_SOURCES,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_TRACK_UNKNOWN_SOURCES
                            )
                        },
                    ): cv.boolean,
                    vol.Optional(
                        CONF_HQ_PLAN_NAME,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_HQ_PLAN_NAME
                            )
                        },
                    ): cv.string,
                    vol.Optional(
                        CONF_APPRECIATION_PHASE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_APPRECIATION_PHASE
                            )
                        },
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_PRE_COLD_PHASE,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_PRE_COLD_PHASE
                            )
                        },
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        description={
                            "suggested_value": self.config_entry.options.get(
                                CONF_SCAN_INTERVAL
                            )
                        },
                    ): (vol.All(cv.positive_int, vol.Range(min=MIN_SCAN_INTERVAL))),
                }
            ),
        )
