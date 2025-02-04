"""Custom OAuth2 implementation."""

import base64
import hashlib
import os
import re
from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from pyhilo.const import AUTH_AUTHORIZE, AUTH_CLIENT_ID, AUTH_TOKEN, DOMAIN
from pyhilo.oauth2helper import OAuth2Helper


class AuthCodeWithPKCEImplementation(LocalOAuth2Implementation):  # type: ignore[misc]
    """Custom OAuth2 implementation."""

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize AuthCodeWithPKCEImplementation."""
        super().__init__(
            hass,
            DOMAIN,
            AUTH_CLIENT_ID,
            "",
            AUTH_AUTHORIZE,
            AUTH_TOKEN,
        )

        self.oauth_helper = OAuth2Helper()

    # ... Override AbstractOAuth2Implementation details
    @property
    def name(self) -> str:
        """Name of the implementation."""
        return "Hilo"

    @property
    def extra_authorize_data(self) -> dict:
        """Extra data that needs to be appended to the authorize url."""
        return self.oauth_helper.get_authorize_parameters()

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        """Resolve the authorization code to tokens."""
        return cast(
            dict,
            await self._token_request(
                self.oauth_helper.get_token_request_parameters(
                    external_data["code"], external_data["state"]["redirect_uri"]
                )
            ),
        )
