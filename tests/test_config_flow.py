"""Tests for the Hilo config flow."""

from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component
from pyhilo.const import AUTH_TOKEN
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from custom_components.hilo.const import CONF_ACCOUNT_LABEL, DOMAIN

from . import ACCOUNT_EMAIL, oauth_token

REDIRECT_URI = "https://example.com/auth/external/callback"
SECOND_EMAIL = "second.account@example.com"


@pytest.fixture(autouse=True)
async def setup_oauth_callback(hass: HomeAssistant) -> None:
    """Serve the OAuth callback view."""
    assert await async_setup_component(hass, "auth", {})


def account_entry(email: str, label: str) -> MockConfigEntry:
    """Return a config entry for an already configured account."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=email,
        data={
            "auth_implementation": DOMAIN,
            "token": oauth_token(email),
            CONF_ACCOUNT_LABEL: label,
        },
        unique_id=email,
        version=2,
        minor_version=2,
    )


async def complete_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    flow_id: str,
    email: str,
) -> ConfigFlowResult:
    """Authorize the given account on an OAuth flow waiting for the callback."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass, {"flow_id": flow_id, "redirect_uri": REDIRECT_URI}
    )
    client = await hass_client_no_auth()
    response = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert response.status == 200
    aioclient_mock.post(AUTH_TOKEN, json=oauth_token(email))
    return await hass.config_entries.flow.async_configure(flow_id)


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
@pytest.mark.parametrize(
    ("existing_accounts", "expected_label"),
    [
        pytest.param([], "", id="first_account_unprefixed"),
        pytest.param([(ACCOUNT_EMAIL, "")], "second.account", id="additional_account"),
        pytest.param(
            [(ACCOUNT_EMAIL, ""), ("second.account@other.com", "second.account")],
            "second.account 2",
            id="label_already_taken",
        ),
    ],
)
async def test_user_flow_creates_account_entry(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    existing_accounts: list[tuple[str, str]],
    expected_label: str,
) -> None:
    """Test each account gets its own entry and a unique entity name label."""
    for email, label in existing_accounts:
        account_entry(email, label).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], SECOND_EMAIL
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SECOND_EMAIL
    assert result["result"].unique_id == SECOND_EMAIL
    assert result["data"][CONF_ACCOUNT_LABEL] == expected_label


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_user_flow_aborts_for_configured_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the same Hilo account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], ACCOUNT_EMAIL
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_updates_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test reauth stores the new token and keeps the account label."""
    entry = account_entry(SECOND_EMAIL, "second.account")
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], SECOND_EMAIL
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"]["refresh_token"] == "mock-refresh-token"
    assert entry.data[CONF_ACCOUNT_LABEL] == "second.account"


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_aborts_for_other_account(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth cannot swap an entry over to a different Hilo account."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], SECOND_EMAIL
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.unique_id == ACCOUNT_EMAIL


@pytest.mark.usefixtures("current_request_with_host", "mock_setup_entry")
async def test_reauth_claims_account_for_entry_without_token(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test an entry migrated from version 1 learns its account on reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"auth_implementation": DOMAIN, CONF_ACCOUNT_LABEL: ""},
        unique_id=DOMAIN,
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    result = await complete_oauth(
        hass, hass_client_no_auth, aioclient_mock, result["flow_id"], ACCOUNT_EMAIL
    )

    assert result["reason"] == "reauth_successful"
    assert entry.unique_id == ACCOUNT_EMAIL
