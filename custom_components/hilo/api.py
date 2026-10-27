"""API for Hilo bound to Home Assistant OAuth."""

from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from pyhilo import AbstractAuth


class AsyncConfigEntryAuth(AbstractAuth):
    """Provide Hilo authentication tied to an OAuth2 based config entry."""

    def __init__(self, oauth_session: OAuth2Session) -> None:
        """Initialize."""
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token, refreshing it first if it expired."""
        await self._oauth_session.async_ensure_token_valid()
        return str(self._oauth_session.token["access_token"])
