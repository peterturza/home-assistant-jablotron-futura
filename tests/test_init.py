"""Tests for the Jablotron Futura integration setup."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.jablotron_futura.const import DOMAIN
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


async def test_unique_id_migration_rewrites_legacy_keys(hass: HomeAssistant):
    """Pre-existing entity registry rows must be migrated to serial-scoped unique_ids."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, create_mock_entry, create_mock_session

    entry = create_mock_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    # Seed a pre-migration registry row with the legacy unique_id.
    legacy = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="filter_health",
        config_entry=entry,
    )
    assert legacy.unique_id == "filter_health"

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    migrated = registry.async_get(legacy.entity_id)
    assert migrated.unique_id == f"{MOCK_SERIAL}_filter_health"


async def test_unique_id_migration_skips_already_prefixed(hass: HomeAssistant):
    """An already serial-prefixed unique_id must be left untouched (idempotent)."""
    from homeassistant.helpers import entity_registry as er
    from .conftest import MOCK_SERIAL, create_mock_entry, create_mock_session

    entry = create_mock_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)

    already_prefixed = f"{MOCK_SERIAL}_filter_health"
    existing = registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=already_prefixed,
        config_entry=entry,
    )

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    after = registry.async_get(existing.entity_id)
    assert after.unique_id == already_prefixed  # no double prefix


async def test_unique_id_migration_isolates_other_entries(hass: HomeAssistant):
    """The migration must not touch registry rows owned by another config entry."""
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.helpers import entity_registry as er
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from .conftest import create_mock_entry, create_mock_session

    other_entry = MockConfigEntry(domain="other_domain", title="other", data={})
    other_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    foreign = registry.async_get_or_create(
        domain="sensor",
        platform="other_domain",
        unique_id="filter_health",
        config_entry=other_entry,
    )

    entry = create_mock_entry()
    entry.add_to_hass(hass)

    mock_session = create_mock_session()
    with patch(
        "custom_components.jablotron_futura.futura.aiohttp_client.async_get_clientsession",
        return_value=mock_session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    after = registry.async_get(foreign.entity_id)
    assert after.unique_id == "filter_health"  # untouched
