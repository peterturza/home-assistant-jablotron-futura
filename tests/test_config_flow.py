"""Tests for the Jablotron Futura config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.jablotron_futura.const import DOMAIN

from .conftest import MOCK_CONFIG, create_mock_session


async def test_config_flow_shows_form(hass: HomeAssistant):
    """Test that the config flow shows the user form initially."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_success(hass: HomeAssistant):
    """Test successful config flow."""
    mock_session = create_mock_session()

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Futura 2"
        assert result["data"] == MOCK_CONFIG
        assert result["result"].unique_id == "SN123456789"


async def test_config_flow_invalid_auth(hass: HomeAssistant):
    """Test config flow with invalid credentials shows auth error."""
    mock_session = create_mock_session(auth_status=401)

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_api_error(hass: HomeAssistant):
    """Test config flow with API error shows unknown error."""
    mock_session = create_mock_session(auth_status=500)

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_CONFIG,
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


async def test_config_flow_aborts_on_duplicate_serial(hass: HomeAssistant):
    """Adding the same Jablotron account twice must abort with 'already_configured'."""
    mock_session = create_mock_session()

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        # First entry succeeds.
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        first = await hass.config_entries.flow.async_configure(first["flow_id"], MOCK_CONFIG)
        assert first["type"] == FlowResultType.CREATE_ENTRY

        # The abort fires on async_configure (when async_set_unique_id runs), not on
        # async_init. Both flows share the same hass, so the first entry persists.

        # Second attempt with the same credentials -> same serial -> abort.
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        second = await hass.config_entries.flow.async_configure(second["flow_id"], MOCK_CONFIG)
        assert second["type"] == FlowResultType.ABORT
        assert second["reason"] == "already_configured"
