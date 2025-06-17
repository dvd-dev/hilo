"""Custom OAuth2 implementation."""

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import LocalOAuth2Implementation

from homeassistant.helpers.aiohttp_client import async_create_clientsession
from aiohttp import CookieJar

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

        self.session = async_create_clientsession(self.hass, cookie_jar=CookieJar(quote_cookie=False))
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

    async def _token_request(self, data: dict) -> dict:
        """Make a token request."""
        data["client_id"] = self.client_id

        if self.client_secret:
            data["client_secret"] = self.client_secret

        resp = await self.session.post(self.token_url, data=data)
        resp.raise_for_status()
        return cast(dict, await resp.json())
