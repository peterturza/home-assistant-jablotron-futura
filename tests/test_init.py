"""Tests for the Jablotron Futura integration setup."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import create_mock_session, setup_integration


async def test_setup_entry(hass: HomeAssistant):
    """Test successful setup of config entry."""
    entry = await setup_integration(hass)

    assert entry.state == ConfigEntryState.LOADED
    assert entry.runtime_data is not None


async def test_setup_entry_auth_failure(hass: HomeAssistant):
    """Test setup fails with auth error."""
    mock_session = create_mock_session(auth_status=401)
    entry = await setup_integration(hass, mock_session)

    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant):
    """Test unloading a config entry."""
    entry = await setup_integration(hass)

    assert entry.state == ConfigEntryState.LOADED

    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
    ):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
