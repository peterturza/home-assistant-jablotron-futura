"""Tests for the Jablotron Futura integration setup."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MockResponse, create_mock_session, setup_integration


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


async def test_authorize_called_once_across_multiple_refreshes(hass: HomeAssistant):
    """Two coordinator refreshes should authorize the session only once."""
    auth_calls = 0
    real_post = create_mock_session().post  # reuse the default mock router

    def counting_post(url, **kwargs):
        nonlocal auth_calls
        if "userAuthorize" in url:
            auth_calls += 1
        return real_post(url, **kwargs)

    mock_session = AsyncMock()
    mock_session.post = counting_post

    entry = await setup_integration(hass, mock_session)
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert auth_calls == 1, f"expected 1 authorize call, got {auth_calls}"


async def test_session_re_authorizes_after_401(hass: HomeAssistant):
    """A 401 from a non-auth call must trigger one fresh authorize + retry."""
    state = {"auth_calls": 0, "device_calls": 0}
    default_session = create_mock_session()

    def post(url, **kwargs):
        if "userAuthorize" in url:
            state["auth_calls"] += 1
            return default_session.post(url, **kwargs)
        if "getDevice" in url:
            state["device_calls"] += 1
            # First call after the initial sync returns 401, then 200.
            if state["device_calls"] == 2:
                return MockResponse({}, status=401)
        return default_session.post(url, **kwargs)

    mock_session = AsyncMock()
    mock_session.post = post

    entry = await setup_integration(hass, mock_session)
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Initial setup = 1 authorize. Refresh hits 401 on getDevice, re-auths
    # once, retries — so 2 total authorize calls expected.
    assert state["auth_calls"] == 2
    assert coordinator.last_update_success is True
    assert coordinator.data is not None
